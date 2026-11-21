"""answer(): one tutor request, one model call at most (docs/tutor_agent.md, section 4)."""
from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from pathlib import Path

from . import checks
from .context import build_context, render
from .models import FREE_HINTS, MODES, ContextProvider, LLMClient, TutorRequest, TutorResponse
from .rules import TEMPLATES, mask, rule_intent

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}, "cited": {"type": "array", "items": {"type": "string"}},
                   "check_question": {"type": "string"}, "mermaid": {"type": ["string", "null"]}},
    "required": ["text", "cited", "check_question"],
}
HISTORY_TURNS, HISTORY_CHARS = 8, 1500
VISUAL_NOTE = ("\n\nThe learner asked for a chart or diagram. Follow the skill below and put the Mermaid code in a "
               "\"mermaid\" field of the same JSON (null if a diagram does not help).\n\n")


def _prompt(version: str) -> str:
    return (PROMPTS / "tutor_small" / f"{version}.md").read_text(encoding="utf-8")


def _parse(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        out = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(out, dict) or not isinstance(out.get("text"), str):
        return None
    out.setdefault("cited", [])
    out.setdefault("check_question", "")
    if not isinstance(out.get("mermaid"), str):
        out["mermaid"] = None
    return out if isinstance(out["cited"], list) and isinstance(out["check_question"], str) else None


def answer(req: TutorRequest, ctx: ContextProvider, llm: LLMClient, denylist: list[str] = ()) -> TutorResponse:
    if req.mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    prompt_version = os.environ.get("PROMPT_VERSION", "tutor-v2")
    hint_level = req.hint_level if req.mode == "hint" else None
    event = {
        "event_id": str(uuid.uuid4()), "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "user_pseudo_id": req.user_id, "task_id": req.task_id, "node": req.node, "mode": req.mode,
        "model_role": "tutor_small", "model": None, "prompt_version": prompt_version, "latency_ms": None,
        "tokens_in": 0, "tokens_out": 0, "checks_failed": [], "fallback_used": False, "hint_level": hint_level,
        "flagged_for_review": False,
    }

    def respond(text, question, intent, fallback=False, links=(), failed=(), mermaid=None):
        event.update(intent=intent, fallback_used=fallback, checks_failed=list(failed),
                     flagged_for_review=bool(failed) or intent in ("advice_request", "injection"))
        return TutorResponse(text=text, links=list(links), check_question=question, hint_level=hint_level,
                             hint_paid=hint_level is not None and hint_level > FREE_HINTS, fallback=fallback,
                             intent=intent, checks_failed=list(failed), event=event, mermaid=mermaid)

    def fallback(intent, failed=()):
        key = req.task_id or req.node
        return respond(ctx.stored_explanation(key, req.mode), "", intent, fallback=True, failed=failed)

    if os.environ.get("TUTOR_ENABLED", "true").lower() != "true":
        return fallback(req.mode)

    message = mask(req.message)
    intent = rule_intent(message) or req.mode
    if intent in TEMPLATES:
        text, question = TEMPLATES[intent]
        return respond(text, question, intent)

    try:
        context = build_context(TutorRequest(**{**req.__dict__, "message": message}), ctx)
    except ValueError:
        return fallback(intent, ["context"])
    context_text = render(context)
    system = _prompt(prompt_version)
    if req.visual:
        system += VISUAL_NOTE + (PROMPTS / "skills" / "mermaid.md").read_text(encoding="utf-8")
    messages = [{"role": "system", "content": system}]
    for turn in req.history[-HISTORY_TURNS:]:  # earlier turns, masked like the new message
        role = "assistant" if turn.get("role") == "tutor" else "user"
        messages.append({"role": role, "content": mask(str(turn.get("text", ""))[:HISTORY_CHARS])})
    messages.append({"role": "user",
                     "content": f"CONTEXT\n{context_text}\n\nMODE: {req.mode}\nLEARNER: {message or '(no message)'}"})

    parsed = None
    for _ in range(2):  # one retry on invalid JSON
        try:
            done = llm.complete("tutor_small", messages, OUTPUT_SCHEMA, max_tokens=400, contains_user_data=True)
        except Exception as e:  # timeout, refused role, provider error: never break the screen
            return fallback(intent, [f"model: {type(e).__name__}"])
        event.update(model=done.model, latency_ms=done.latency_ms, tokens_in=event["tokens_in"] + done.tokens_in,
                     tokens_out=event["tokens_out"] + done.tokens_out)
        parsed = _parse(done.text)
        if parsed:
            break
    if not parsed:
        return fallback(intent, ["invalid json"])

    labels = [p["label"] for p in context["passages"]]
    # numbers the learner typed may be repeated back
    failed = (checks.check_numbers(parsed["text"], context_text + " " + message)
              + checks.check_advice(parsed["text"], list(denylist))
              + checks.check_citations(parsed["cited"], labels)
              + checks.check_form(parsed["text"], parsed["check_question"]))
    if req.mode in ("hint", "explain_concept") and req.task_id:
        failed += checks.check_leak(parsed["text"], ctx.task_secrets(req.task_id))
    if failed:
        return fallback(intent, failed)

    by_label = {p["label"]: p for p in context["passages"]}
    links = [{"label": c, "url": by_label[c].get("url")} for c in parsed["cited"]]
    return respond(parsed["text"], parsed["check_question"], intent, links=links,
                   mermaid=parsed["mermaid"] if req.visual else None)
