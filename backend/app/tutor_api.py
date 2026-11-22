"""POST /tutor: the AI tutor (docs/tutor_agent.md, section 5), a first slice.

- Answers in plain words, using the question context the app sends (question,
  the learner's answer, the right answer, the explanation).
- Charts and diagrams: when the learner asks for one, the Mermaid skill
  (ml/prompts/skills/mermaid.md) is added to the prompt and the model returns
  Mermaid code. The code is checked here (allowed diagram types, no unsafe
  directives); the app then parses and renders it, and asks for a repair
  (mode "repair_diagram") if Mermaid rejects it. The learner never sees raw code.
- Every call is logged to llm_events with masked text, for the admin panel.
- Falls back to the stored explanation when the model is off or unreachable.

The model runs in Ollama (OLLAMA_API_BASE, TUTOR_MODEL). Mateusz's full tutor
pipeline (backend/ml/tutor, LiteLLM, output checks) can replace call_model().
"""
import hashlib
import json
import os
import threading
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import tutor_pipeline
from app.admin import log_llm_event
from app.db import get_db
from app.deps import ApiError, current_user, is_guest, viewer
from app.models import LlmEvent, TutorCache, User

router = APIRouter(tags=["tutor"])

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434")
TUTOR_MODEL = os.getenv("TUTOR_MODEL", "gemma4:12b")
TUTOR_ENABLED = os.getenv("TUTOR_ENABLED", "true").lower() != "false"
# Label of this file's own tutor prompt in llm_events. PROMPT_VERSION (tutor-v2) is read by the tutor pipeline.
MO_PROMPT_VERSION = os.getenv("MO_PROMPT_VERSION", "mo-v1")
TUTOR_TIMEOUT = float(os.getenv("TUTOR_TIMEOUT", "90"))  # seconds; the first call also loads the model
SKILL_DIR = Path(__file__).resolve().parent.parent / "ml" / "prompts" / "skills"

VISUAL = re.compile(r"\b(chart|graph|plot|diagram|figure|visuali[sz]e|draw|flow ?chart|pie|timeline|bar|line chart|picture)\b", re.I)
ADVICE = re.compile(r"\b(should i (buy|sell)|which (stock|share|etf|fund) (should|to)|recommend (a|me)|will .{0,30}(go up|rise|fall)|best (stock|fund|etf))\b", re.I)
MERMAID_TYPES = ("xychart-beta", "pie", "flowchart", "graph", "timeline")
FORBIDDEN = re.compile(r"(click\s|call\s|href|javascript:|%%\{|<\s*script|<br|url\()", re.I)

SYSTEM = """You are the CrocoCash tutor, a patient teacher of personal investing basics for people in Poland.
- Explain ideas in plain words, in 2 to 5 short sentences. Be warm and conversational.
- Use the question context when it is given: the question, the learner's answer, the right answer and the explanation.
- Never recommend a product, a fund, a stock or a ticker, and never predict prices. Teach how to judge a choice instead.
- If asked for advice, say you can't give it and offer to explain the idea behind it.
Reply as JSON: {"text": "...", "mermaid": null}."""


class TutorIn(BaseModel):
    mode: str = "explain_concept"           # explain_concept | explain_result | repair_diagram
    message: str = Field(max_length=2000)
    context: dict | None = None
    history: list[dict] = Field(default_factory=list)


def mask(text: str | None) -> str | None:
    """Remove obvious personal data before storing text (emails, phones, IBAN, PESEL)."""
    if not text:
        return text
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email]", text)
    text = re.sub(r"\bPL\d{26}\b|\b\d{26}\b", "[iban]", text)
    text = re.sub(r"\b\d{11}\b", "[pesel]", text)
    text = re.sub(r"(\+?\d[\d \-]{7,}\d)", "[phone]", text)
    return text


def clean_mermaid(code: str | None) -> str | None:
    """Strip fences and reject anything that is not an allowed, safe diagram."""
    if not code or not isinstance(code, str):
        return None
    code = re.sub(r"^```(?:mermaid)?\s*|\s*```$", "", code.strip(), flags=re.M).strip()
    first = code.splitlines()[0].strip().lower() if code else ""
    if not first.startswith(MERMAID_TYPES) or FORBIDDEN.search(code) or len(code) > 3000:
        return None
    return code


def parse_reply(content: str) -> dict:
    """The model is asked for JSON but some local models can't force it: take the
    first {...} block, strip ``` fences, and fall back to plain text."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.M)
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            if isinstance(d, dict):
                return d
        except json.JSONDecodeError:
            pass
    return {"text": text, "mermaid": None}


def _ollama_headers() -> dict:
    """Content type plus OLLAMA_HEADERS (JSON), e.g. a Cloudflare Access service token or a bearer token
    for a proxy in front of Ollama, which has no authentication of its own."""
    try:
        extra = json.loads(os.getenv("OLLAMA_HEADERS") or "{}")
    except ValueError:
        extra = {}
    return {"Content-Type": "application/json", **{str(k): str(v) for k, v in (extra if isinstance(extra, dict) else {}).items()}}


_last = threading.local()  # Ollama timings of the last call on this thread (call_model keeps its signature)


def _timings(out: dict) -> dict:
    """Ollama's durations (nanoseconds) as milliseconds, for llm_events."""
    ms = lambda k: int(out[k] / 1e6) if isinstance(out.get(k), (int, float)) else None
    return {"load_ms": ms("load_duration"), "prompt_eval_ms": ms("prompt_eval_duration"), "eval_ms": ms("eval_duration")}


# ---------------------------------------------------------------- answer cache (docs/scaling.md, layer 2)
CACHE_TTL = timedelta(days=1)


def cache_key(body: "TutorIn") -> str | None:
    """Only answers that are the same for everyone: explain_concept with no history, no task attempt,
    and a message that masking leaves unchanged (no personal data). A first question in the tutor chat
    has no node; it is cached under "-". None means: do not cache."""
    ctx = body.context or {}
    if body.mode != "explain_concept" or body.history or ctx.get("task_id") \
            or ctx.get("picked") is not None or mask(body.message) != body.message:
        return None
    version = os.getenv("PROMPT_VERSION", "tutor-v2") if tutor_pipeline.handles(body.mode) else MO_PROMPT_VERSION
    norm = " ".join(body.message.lower().split())
    return hashlib.sha256(f"{version}|{TUTOR_MODEL}|{body.mode}|{ctx.get('node') or '-'}|{norm}".encode()).hexdigest()


def cache_get(db: Session, key: str | None):
    if not key:
        return None
    row = db.get(TutorCache, key)
    if row is None:
        return None
    created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created > CACHE_TTL:
        db.delete(row)
        return None
    row.hits = (row.hits or 0) + 1
    return row


def cache_put(db: Session, key: str | None, body: "TutorIn", text: str, mermaid: str | None) -> None:
    if key and text:
        db.merge(TutorCache(key=key, mode=body.mode, node=(body.context or {}).get("node"), text=text, mermaid=mermaid,
                            hits=0, created_at=datetime.now(timezone.utc)))


def call_model(messages: list[dict]) -> tuple[dict, int, int, int]:
    """One chat call to Ollama in JSON mode. Returns (parsed, latency_ms, tokens_in, tokens_out)."""
    # think=False: Gemma 4 otherwise reasons privately for ~50 s before answering.
    body = json.dumps({"model": TUTOR_MODEL, "messages": messages, "stream": False, "think": False,
                       "keep_alive": "30m", "options": {"temperature": 0.3}}).encode()
    req = urllib.request.Request(f"{OLLAMA_API_BASE}/api/chat", data=body, headers=_ollama_headers())
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=TUTOR_TIMEOUT) as r:
        out = json.loads(r.read())
    latency = int((time.monotonic() - t0) * 1000)
    if "error" in out:
        raise OSError(out["error"])
    _last.timings = _timings(out)
    parsed = parse_reply(out.get("message", {}).get("content", ""))
    return parsed, latency, out.get("prompt_eval_count") or 0, out.get("eval_count") or 0


def build_messages(body: TutorIn, visual: bool) -> list[dict]:
    system = SYSTEM
    if visual or body.mode == "repair_diagram":
        system += "\n\n" + (SKILL_DIR / "mermaid.md").read_text()
    msgs = [{"role": "system", "content": system}]
    if body.context:
        ctx = {k: v for k, v in body.context.items() if v not in (None, "") and k in
               ("question", "picked", "correct", "explanation", "was_right", "node", "mermaid")}
        msgs.append({"role": "system", "content": "Question context: " + json.dumps(ctx, ensure_ascii=False)})
    # Personal data is masked before it reaches the model, not only in the logs.
    for h in body.history[-8:]:
        role = "assistant" if h.get("role") == "tutor" else "user"
        msgs.append({"role": role, "content": mask(str(h.get("text", "")))[:1500]})
    if body.mode == "title":
        return [{"role": "system", "content": "Write a short title (2 to 6 words, no quotes, no final period) for this tutor "
                 "conversation. Reply as JSON: {\"text\": \"<title>\", \"mermaid\": null}."},
                {"role": "user", "content": mask(body.message)[:1500]}]
    if body.mode == "repair_diagram":
        msgs.append({"role": "user", "content": "Mermaid could not render your diagram. Error: " + mask(body.message)
                     + ". Return the same JSON with a corrected, simpler 'mermaid' value that follows the skill exactly."})
    else:
        msgs.append({"role": "user", "content": mask(body.message)})
    return msgs


# Limits on tutor calls: each one is a model call on a shared GPU.
TUTOR_PER_MINUTE = int(os.getenv("TUTOR_PER_MINUTE", "8"))  # per user (guests: per IP), sliding minute
DAILY_BUDGET = int(os.getenv("DAILY_BUDGET", "80"))  # tutor calls per user (guests: per IP) and UTC day; 0 = no limit
_minute: dict[str, list[float]] = {}
_guest_day: dict[str, tuple[str, int]] = {}  # ip -> (day, calls); accounts are counted from llm_events instead
_limit_lock = threading.Lock()


def client_ip(request: Request) -> str:
    """The visitor's address. Traffic arrives through Cloudflare Tunnel and Caddy, so the socket peer is
    always local; Cloudflare puts the real one in CF-Connecting-IP (the origin is reachable only
    through the tunnel, so the header cannot be set from outside)."""
    h = request.headers
    ip = h.get("cf-connecting-ip") or (h.get("x-forwarded-for") or "").split(",")[0].strip()
    return ip or (request.client.host if request.client else "-")


def tutor_limit(user, request: Request, db: Session, mode: str) -> None:
    """429 when a learner sends too many tutor messages in a minute or uses up the day's budget.
    Chat titles are tiny and automatic, so they do not count."""
    if mode == "title":
        return
    guest = is_guest(user)
    who = f"ip:{client_ip(request)}" if guest else f"u:{user.id}"
    now, day = time.monotonic(), datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _limit_lock:
        hits = [t for t in _minute.get(who, []) if now - t < 60]
        if len(hits) >= TUTOR_PER_MINUTE:
            raise ApiError(429, "rate_limited", "That is a lot of questions in one minute. Take a breath and ask again in a moment.")
        if DAILY_BUDGET and guest:
            d, n = _guest_day.get(who, (day, 0))
            n = n if d == day else 0
            if n >= DAILY_BUDGET:
                raise ApiError(429, "daily_budget", "Kyle has answered a lot of questions today. Come back tomorrow, or read the cards for this topic.")
            _guest_day[who] = (day, n + 1)
        hits.append(now)
        _minute[who] = hits
    if DAILY_BUDGET and not guest:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        used = db.scalar(select(func.count(LlmEvent.id)).where(LlmEvent.user_id == user.id, LlmEvent.ts >= start,
                                                               LlmEvent.mode != "title"))
        if (used or 0) >= DAILY_BUDGET:
            raise ApiError(429, "daily_budget", "Kyle has answered a lot of questions today. Come back tomorrow, or read the cards for this topic.")


def _log(db, user, **kw):
    """Tutor calls are logged for accounts only; guests are never stored."""
    if not is_guest(user):
        log_llm_event(db, user, **kw)


@router.post("/tutor")
def tutor(body: TutorIn, request: Request, user=Depends(viewer), db: Session = Depends(get_db)):
    tutor_limit(user, request, db, body.mode)
    visual = bool(VISUAL.search(body.message)) and body.mode != "repair_diagram"
    t0, key = time.monotonic(), cache_key(body)
    hit = cache_get(db, key)
    if hit is not None:
        _log(db, user, mode=body.mode, model_role="tutor_small", model="cache", node=hit.node, prompt_masked=body.message,
             latency_ms=int((time.monotonic() - t0) * 1000), checks_failed=[], fallback_used=False, flagged_for_review=False,
             answer_masked=hit.text)
        db.commit()
        return {"text": hit.text, "mermaid": hit.mermaid, "fallback": False, "cached": True}
    if tutor_pipeline.handles(body.mode):  # TUTOR_PIPELINE=true: server-side context and output checks
        out = tutor_pipeline.run(body, user, db, call_model, TUTOR_MODEL, visual, clean_mermaid)
        if not out.get("fallback") and not out.get("template"):  # templates are instant, keep them out of the cache
            cache_put(db, key, body, out.get("text") or "", out.get("mermaid"))
            db.commit()
        return out
    intent = "advice_request" if ADVICE.search(body.message) else ("visualize" if visual else "question")
    stored = (body.context or {}).get("explanation")
    log = dict(mode=body.mode, intent=intent, model_role="tutor_small", model=f"ollama/{TUTOR_MODEL}",
               prompt_version=MO_PROMPT_VERSION, node=(body.context or {}).get("node"), task_id=(body.context or {}).get("task_id"),
               prompt_masked=mask(body.message))
    if not TUTOR_ENABLED:
        text = stored or "The tutor is resting right now. Here is the key idea from the lesson instead."
        _log(db, user, **log, fallback_used=True, checks_failed=[], flagged_for_review=False, answer_masked=mask(text))
        db.commit()
        return {"text": text, "mermaid": None, "fallback": True}
    try:
        parsed, latency, t_in, t_out = call_model(build_messages(body, visual))
    except (urllib.error.URLError, TimeoutError, OSError):
        text = stored or "I can't reach the tutor model right now. Try again in a moment."
        _log(db, user, **log, fallback_used=True, checks_failed=["model_unreachable"], flagged_for_review=False,
                      answer_masked=mask(text))
        db.commit()
        return {"text": text, "mermaid": None, "fallback": True}
    text = str(parsed.get("text") or "").strip() or (stored or "")
    raw = parsed.get("mermaid")
    mermaid = clean_mermaid(raw)
    failed = []
    if (visual or body.mode == "repair_diagram") and raw and not mermaid:
        failed.append("diagram_rejected")
    if ADVICE.search(text):
        failed.append("advice")
        text = stored or "I can't recommend products or predict prices, but I can explain how to compare options. Which idea should we look at?"
    flagged = bool(failed) or intent == "advice_request"
    _log(db, user, **log, latency_ms=latency, tokens_in=t_in, tokens_out=t_out, checks_failed=failed,
                  fallback_used=False, flagged_for_review=flagged, answer_masked=mask(text + (f"\n[diagram]\n{mermaid}" if mermaid else "")),
         **getattr(_last, "timings", {}))
    if not failed:
        cache_put(db, key, body, text, mermaid)
    db.commit()
    return {"text": text, "mermaid": mermaid, "fallback": False}


# ---------------------------------------------------------------- streaming

STREAM_RULES = """
Write your answer as plain text (not JSON), 2 to 5 short sentences.
If the learner asked for a chart or diagram, write the explanation first, then the Mermaid code
inside one fenced block at the very end:
```mermaid
...
```"""


def _stream_messages(body: TutorIn, visual: bool) -> list[dict]:
    msgs = build_messages(body, visual)
    msgs[0] = {"role": "system", "content": msgs[0]["content"].replace('Reply as JSON: {"text": "...", "mermaid": null}.', "")
               + ("\n\nIgnore the JSON output format above." if visual else "") + STREAM_RULES}
    return msgs


@router.post("/tutor/stream")
def tutor_stream(body: TutorIn, request: Request, user=Depends(viewer), db: Session = Depends(get_db)):
    """Like POST /tutor, but streams the reply as NDJSON lines while the model writes it:
    {"t": "delta", "text": "..."} for each piece of visible text, then one
    {"t": "done", "text": <final text>, "mermaid": <checked code or null>, "fallback": bool}.
    The Mermaid block is never streamed; it is checked and sent once, in "done"."""
    from fastapi.responses import StreamingResponse
    from app.db import SessionLocal

    tutor_limit(user, request, db, body.mode)

    visual = bool(VISUAL.search(body.message))
    intent = "advice_request" if ADVICE.search(body.message) else ("visualize" if visual else "question")
    stored = (body.context or {}).get("explanation")
    log = dict(mode=body.mode, intent=intent, model_role="tutor_small", model=f"ollama/{TUTOR_MODEL}",
               prompt_version=MO_PROMPT_VERSION, node=(body.context or {}).get("node"), task_id=(body.context or {}).get("task_id"),
               prompt_masked=mask(body.message))

    def line(obj) -> bytes:
        return (json.dumps(obj, ensure_ascii=False) + "\n").encode()

    key = cache_key(body)
    with SessionLocal() as db:
        hit = cache_get(db, key)
        if hit is not None:
            text, mermaid, node = hit.text, hit.mermaid, hit.node
            _log(db, user, mode=body.mode, model_role="tutor_small", model="cache", node=node, prompt_masked=body.message,
                 latency_ms=0, checks_failed=[], fallback_used=False, flagged_for_review=False, answer_masked=text)
            db.commit()

            def cached():
                yield line({"t": "delta", "text": text})
                yield line({"t": "done", "text": text, "mermaid": mermaid, "fallback": False, "cached": True})
            return StreamingResponse(cached(), media_type="application/x-ndjson",
                                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    if tutor_pipeline.handles(body.mode):
        # The output checks need the whole answer, so with the pipeline the text arrives in one piece:
        # the same NDJSON contract, one "delta" (unless it is a fallback) and the "done" line.
        def checked():
            with SessionLocal() as db:
                out = tutor_pipeline.run(body, user, db, call_model, TUTOR_MODEL, visual, clean_mermaid)
                if not out.get("fallback") and not out.get("template"):
                    cache_put(db, key, body, out.get("text") or "", out.get("mermaid"))
                    db.commit()
            if not out["fallback"]:
                yield line({"t": "delta", "text": out["text"]})
            yield line({"t": "done", **out})
        return StreamingResponse(checked(), media_type="application/x-ndjson",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    def finish(text, mermaid, fallback, failed, latency=None, t_in=None, t_out=None, timings=None):
        with SessionLocal() as db:  # the request's session is closed once streaming starts
            _log(db, user, **log, latency_ms=latency, tokens_in=t_in, tokens_out=t_out, checks_failed=failed,
                          fallback_used=fallback, flagged_for_review=bool(failed) or intent == "advice_request",
                          answer_masked=mask(text + (f"\n[diagram]\n{mermaid}" if mermaid else "")), **(timings or {}))
            if not fallback and not failed:
                cache_put(db, key, body, text, mermaid)
            db.commit()
        return line({"t": "done", "text": text, "mermaid": mermaid, "fallback": fallback})

    def gen():
        if not TUTOR_ENABLED:
            yield finish(stored or "The tutor is resting right now.", None, True, [])
            return
        req = urllib.request.Request(
            f"{OLLAMA_API_BASE}/api/chat",
            data=json.dumps({"model": TUTOR_MODEL, "messages": _stream_messages(body, visual), "stream": True, "think": False,
                             "keep_alive": "30m", "options": {"temperature": 0.3}}).encode(),
            headers=_ollama_headers())
        full, sent, t0, t_in, t_out, timings = "", 0, time.monotonic(), 0, 0, {}
        try:
            with urllib.request.urlopen(req, timeout=TUTOR_TIMEOUT) as r:
                for raw in r:
                    if not raw.strip():
                        continue
                    chunk = json.loads(raw)
                    if "error" in chunk:
                        raise OSError(chunk["error"])
                    full += chunk.get("message", {}).get("content", "")
                    if chunk.get("done"):
                        t_in, t_out = chunk.get("prompt_eval_count") or 0, chunk.get("eval_count") or 0
                        timings = _timings(chunk)
                    visible = full.split("```", 1)[0]
                    if "```" not in full:
                        visible = visible.rstrip("`")  # hold back a fence that may be starting
                    if len(visible) > sent:
                        yield line({"t": "delta", "text": visible[sent:]})
                        sent = len(visible)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            if not full:
                yield finish(stored or "I can't reach the tutor model right now. Try again in a moment.", None, True,
                             ["model_unreachable"])
                return
        text = full.split("```", 1)[0].strip()
        m = re.search(r"```(?:mermaid)?\s*\n(.*?)(?:```|$)", full, re.S)
        mermaid = clean_mermaid(m.group(1)) if m else None
        failed = ["diagram_rejected"] if m and not mermaid else []
        if ADVICE.search(text):
            failed.append("advice")
            text = stored or "I can't recommend products or predict prices, but I can explain how to compare options."
        yield finish(text or (stored or ""), mermaid, False, failed, int((time.monotonic() - t0) * 1000), t_in, t_out, timings)

    return StreamingResponse(gen(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
