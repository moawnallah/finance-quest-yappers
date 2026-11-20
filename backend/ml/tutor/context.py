"""Context by mode (docs/tutor_agent.md, section 4). This is the main guard: what the model never
receives, it cannot leak. Truth values and box weights reach the model only through the reveal,
and only in explain_result."""
from __future__ import annotations

import json

from .models import ContextProvider, TutorRequest

PASSAGES = 3


def build_context(req: TutorRequest, ctx: ContextProvider) -> dict:
    """Return {"fields": {...} for the prompt, "passages": [...] labelled K1..}. Raises ValueError
    when the mode cannot be served (e.g. explain_result before submission)."""
    fields: dict = {"mode": req.mode, "node": req.node}
    if req.mode == "rephrase":
        if not req.last_answer:
            raise ValueError("rephrase needs the last answer")
        fields["text_to_rephrase"] = req.last_answer
        return {"fields": fields, "passages": []}

    fields["learner"] = ctx.profile_aggregates(req.user_id)
    if req.task_id and req.mode in ("explain_concept", "hint", "explain_result"):
        fields["task"] = ctx.task_public(req.task_id)
    if req.mode in ("hint", "explain_result") and req.draft_response is not None:
        fields["user_response"] = req.draft_response
    if req.mode == "hint":
        fields["hint_level"] = req.hint_level
    if req.mode == "explain_result":
        reveal = ctx.reveal(req.attempt_id) if req.attempt_id else None
        if reveal is None:
            raise ValueError("explain_result needs a submitted attempt")
        fields["reveal"] = reveal

    query = " ".join(filter(None, [req.message, json.dumps(fields.get("task", ""))]))
    passages = ctx.search_kb(req.node, query, PASSAGES)
    labelled = [{**p, "label": f"K{i + 1}"} for i, p in enumerate(passages)]
    return {"fields": fields, "passages": labelled}


def render(context: dict) -> str:
    """The CONTEXT block of the prompt. Numbers the model may use must appear here."""
    parts = [json.dumps(context["fields"], ensure_ascii=False, indent=1)]
    for p in context["passages"]:
        parts.append(f"[{p['label']}] {p['body']}")
    return "\n\n".join(parts)
