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
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.admin import log_llm_event
from app.db import get_db
from app.deps import current_user
from app.models import User

router = APIRouter(tags=["tutor"])

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434")
TUTOR_MODEL = os.getenv("TUTOR_MODEL", "gemma4:12b")
TUTOR_ENABLED = os.getenv("TUTOR_ENABLED", "true").lower() != "false"
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "tutor-v1")
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


def call_model(messages: list[dict]) -> tuple[dict, int, int, int]:
    """One chat call to Ollama in JSON mode. Returns (parsed, latency_ms, tokens_in, tokens_out)."""
    body = json.dumps({"model": TUTOR_MODEL, "messages": messages, "stream": False, "format": "json",
                       "options": {"temperature": 0.3}}).encode()
    req = urllib.request.Request(f"{OLLAMA_API_BASE}/api/chat", data=body, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.loads(r.read())
    latency = int((time.monotonic() - t0) * 1000)
    content = out.get("message", {}).get("content", "{}")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"text": content, "mermaid": None}
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
    for h in body.history[-8:]:
        role = "assistant" if h.get("role") == "tutor" else "user"
        msgs.append({"role": role, "content": str(h.get("text", ""))[:1500]})
    if body.mode == "repair_diagram":
        msgs.append({"role": "user", "content": "Mermaid could not render your diagram. Error: " + body.message
                     + ". Return the same JSON with a corrected, simpler 'mermaid' value that follows the skill exactly."})
    else:
        msgs.append({"role": "user", "content": body.message})
    return msgs


@router.post("/tutor")
def tutor(body: TutorIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    visual = bool(VISUAL.search(body.message)) and body.mode != "repair_diagram"
    intent = "advice_request" if ADVICE.search(body.message) else ("visualize" if visual else "question")
    stored = (body.context or {}).get("explanation")
    log = dict(mode=body.mode, intent=intent, model_role="tutor_small", model=f"ollama/{TUTOR_MODEL}",
               prompt_version=PROMPT_VERSION, node=(body.context or {}).get("node"), task_id=(body.context or {}).get("task_id"),
               prompt_masked=mask(body.message))
    if not TUTOR_ENABLED:
        text = stored or "The tutor is resting right now. Here is the key idea from the lesson instead."
        log_llm_event(db, user, **log, fallback_used=True, checks_failed=[], flagged_for_review=False, answer_masked=mask(text))
        db.commit()
        return {"text": text, "mermaid": None, "fallback": True}
    try:
        parsed, latency, t_in, t_out = call_model(build_messages(body, visual))
    except (urllib.error.URLError, TimeoutError, OSError):
        text = stored or "I can't reach the tutor model right now. Try again in a moment."
        log_llm_event(db, user, **log, fallback_used=True, checks_failed=["model_unreachable"], flagged_for_review=False,
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
    log_llm_event(db, user, **log, latency_ms=latency, tokens_in=t_in, tokens_out=t_out, checks_failed=failed,
                  fallback_used=False, flagged_for_review=flagged, answer_masked=mask(text + (f"\n[diagram]\n{mermaid}" if mermaid else "")))
    db.commit()
    return {"text": text, "mermaid": mermaid, "fallback": False}
