"""Our tutor pipeline (backend/ml/tutor, docs/tutor_agent.md) behind POST /tutor and /tutor/stream.

Reader: whoever maintains app/tutor_api.py. That module keeps the HTTP contract, the Ollama call,
the Mermaid checks and the logging; this one adds what the pipeline brings:
- context built on the server per mode: before an answer is submitted the model never sees it;
  after submission (an Attempt row exists) it gets the reveal. The app's own context is used only
  for the node and task id;
- the rule layer (advice and prompt-injection templates) and the five output checks (invented
  numbers, advice, answer leaks, citations, form), with the stored explanation as fallback;
- card passages as sources, returned as `links`.

Switched by TUTOR_PIPELINE (default off, so merging changes nothing until a test environment turns
it on). Modes it serves: explain_concept, hint, explain_result, rephrase. Titles and diagram repair
stay in tutor_api.py.
"""
import json
import os
import re
import sys
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin import log_llm_event
from app.config import BACKEND_DIR, SERVE_DRAFTS
from app.engines import catalog, easy, hard, medium
from app.models import Attempt, Onboarding, User

ML_DIR = BACKEND_DIR / "ml"
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from tutor import Completion, TutorRequest, answer, kb  # noqa: E402
from tutor.rules import mask  # noqa: E402

PIPELINE_MODES = {"explain_concept", "hint", "explain_result", "rephrase"}
CITATION = re.compile(r"\s*\[K\d+\]")


def enabled() -> bool:
    return os.getenv("TUTOR_PIPELINE", "false").lower() == "true"


def handles(mode: str) -> bool:
    return enabled() and mode in PIPELINE_MODES


class OllamaClient:
    """The pipeline's LLMClient on top of tutor_api.call_model (Gemma in Ollama, thinking off)."""

    def __init__(self, call, model: str):
        self.call, self.model = call, model

    def complete(self, role, messages, json_schema, max_tokens, contains_user_data) -> Completion:
        parsed, latency, t_in, t_out = self.call(messages)
        return Completion(text=json.dumps(parsed, ensure_ascii=False), model=f"ollama/{self.model}",
                          tokens_in=t_in, tokens_out=t_out, latency_ms=latency)


# ---------------------------------------------------------------- content the context is built from

@lru_cache(maxsize=1)
def _content() -> tuple[list[dict], dict[str, list[str]], dict[str, dict]]:
    """(card passages, prerequisites per node, nodes). Drafts are served only when SERVE_DRAFTS is on."""
    nodes = kb.load_nodes()
    passages = kb.passages_from_cards(nodes, kb.load_sources()) if SERVE_DRAFTS else kb.ingest()[0]
    return passages, {n: d.get("after") or [] for n, d in nodes.items()}, nodes


def _public(level: str, rec: dict) -> dict:
    """What the model may see before submission: the question, never the answer or the data series."""
    if level == "easy":
        q = easy.question_view(rec)
        return {"id": rec["id"], "question": q["q"], "options": q.get("options")}
    if level == "medium":
        q = medium.question_view(rec)
        return {"id": rec["id"], "brief": q["brief"], "response": q["response"],
                "reasons": [b["text"] for b in q["reasons"]["boxes"]]}
    q = hard.question_view(rec)
    return {"id": rec["id"], "brief": q["brief"], "assets": q.get("assets"), "values": q.get("vars"),
            "tests": q.get("obligatory"), "assumptions": q.get("assumptions")}


def _reveal(level: str, rec: dict) -> dict:
    if level == "easy":
        r = easy.reveal_view(rec)
        return {"answer": r["answer"], "why": r["why"]}
    if level == "medium":
        r, q = medium.reveal_view(rec), medium.question_view(rec)
        texts = {b["id"]: b["text"] for b in q["reasons"]["boxes"]}
        return {"text": r["text"], "outcome": r.get("outcome"), "truth": r.get("truth"),
                "reasons": [{"text": texts.get(b["id"]), "weight": b.get("weight"), "explain": b.get("explain")}
                            for b in r.get("reasons") or []]}
    return {"editorial": hard.reveal_view(rec)["editorial"]}


def _medium_secrets(rec: dict) -> dict:
    """The medium engine has no secrets(): the good reason texts, the outcome's change and a numeric truth."""
    r, q = medium.reveal_view(rec), medium.question_view(rec)
    texts = {b["id"]: b["text"] for b in q["reasons"]["boxes"]}
    strings = [texts[b["id"]] for b in r.get("reasons") or [] if (b.get("weight") or 0) > 0 and b["id"] in texts]
    outcome, truth = r.get("outcome") or {}, r.get("truth")
    numbers = [abs(outcome["change"])] if isinstance(outcome.get("change"), (int, float)) else []
    numbers += [abs(truth)] if isinstance(truth, (int, float)) and not isinstance(truth, bool) else []
    return {"strings": strings, "numbers": numbers}


class DbContext:
    """The pipeline's ContextProvider, reading the catalog and this user's rows only."""

    def __init__(self, db: Session, user: User):
        self.db, self.user = db, user

    def _find(self, task_id: str) -> tuple[str, dict]:
        found = catalog().find(task_id)
        if not found:
            raise ValueError(f"no task {task_id!r}")  # the pipeline answers with the fallback
        return found

    def task_public(self, task_id: str) -> dict:
        return _public(*self._find(task_id))

    def reveal(self, attempt_id: str) -> dict | None:
        a = self.db.get(Attempt, int(attempt_id))
        if a is None or a.user_id != self.user.id:
            return None
        level, rec = self._find(a.task_id)
        return {**_reveal(level, rec), "learner_response": a.response, "score": a.score, "points": a.points}

    def task_secrets(self, task_id: str) -> dict:
        level, rec = self._find(task_id)
        return {"easy": easy.secrets, "medium": _medium_secrets, "hard": hard.secrets}[level](rec)

    def profile_aggregates(self, user_id: str) -> dict:
        o = self.db.get(Onboarding, user_id)
        if o is None:
            return {}
        path = [p["node"] for p in o.result.get("path", [])]
        return {"age_band": o.survey.get("age_band"), "goal": o.survey.get("goal"), "horizon": o.survey.get("horizon"),
                "knowledge_band": o.result.get("band"),
                "mastery": {k: v for k, v in (o.result.get("mastery") or {}).items() if k in path}}

    def search_kb(self, node: str, query: str, k: int) -> list[dict]:
        passages, prereq, _ = _content()
        if node:
            return kb.search(passages, node, query, k, prereq)
        terms = kb._terms(query)  # free chat without a node: the best-matching cards of any node
        return sorted(passages, key=lambda p: -len(terms & kb._terms(p["body"])))[:k]

    def stored_explanation(self, key: str, mode: str) -> str:
        found = catalog().find(key)
        if found and mode == "explain_result":  # the explanation is the answer: only after submission
            level, rec = found
            r = _reveal(level, rec)
            return r.get("why") or r.get("text") or r.get("editorial") or ""
        node = found[1]["node"] if found else key
        cards = (_content()[2].get(node) or {}).get("cards") or []
        return cards[0]["body"] if cards else "Open the cards for this topic: the key idea is explained there."


# ---------------------------------------------------------------- one request

def _submitted(db: Session, user: User, task_id: str) -> Attempt | None:
    return db.scalars(select(Attempt).where(Attempt.user_id == user.id, Attempt.task_id == task_id)
                      .order_by(Attempt.id.desc()).limit(1)).first()


def run(body, user: User, db: Session, call, model: str, visual: bool, clean_mermaid) -> dict:
    """Answer one tutor request with the pipeline, log it to llm_events, and return the /tutor reply."""
    ctx_in = body.context or {}
    task_id = ctx_in.get("task_id")
    found = catalog().find(task_id) if task_id else None
    task_id = task_id if found else None
    node = ctx_in.get("node") or (found[1]["node"] if found else "")
    attempt = _submitted(db, user, task_id) if task_id else None

    mode = body.mode
    if mode in ("explain_concept", "explain_result"):
        # The server decides: with a stored attempt the learner has seen the answer, so the reveal may be used;
        # without one, never, whatever the app says.
        mode = "explain_result" if attempt else "explain_concept"
    req = TutorRequest(mode=mode, user_id=user.id, node=node, message=body.message, task_id=task_id,
                       attempt_id=str(attempt.id) if attempt else None,
                       hint_level=int(ctx_in.get("hint_level") or 1), draft_response=ctx_in.get("draft"),
                       last_answer=ctx_in.get("last_answer"), history=body.history, visual=visual)
    resp = answer(req, DbContext(db, user), OllamaClient(call, model))

    mermaid = clean_mermaid(resp.mermaid) if resp.mermaid else None
    failed = list(resp.checks_failed) + (["diagram_rejected"] if resp.mermaid and not mermaid else [])
    text = CITATION.sub("", resp.text).strip()
    if resp.check_question and not resp.fallback:
        text = f"{text}\n\n{resp.check_question}"
    e = resp.event
    log_llm_event(db, user, mode=mode, intent=resp.intent, model_role="tutor_small", model=e.get("model") or f"ollama/{model}",
                  prompt_version=e.get("prompt_version"), node=node or None, task_id=task_id,
                  latency_ms=e.get("latency_ms"), tokens_in=e.get("tokens_in"), tokens_out=e.get("tokens_out"),
                  checks_failed=failed, fallback_used=resp.fallback, flagged_for_review=e.get("flagged_for_review") or bool(failed),
                  hint_level=resp.hint_level, prompt_masked=mask(body.message),
                  answer_masked=mask(text + (f"\n[diagram]\n{mermaid}" if mermaid else "")))
    db.commit()
    return {"text": text, "mermaid": mermaid, "fallback": resp.fallback, "links": resp.links,
            "check_question": resp.check_question, "hint_level": resp.hint_level, "hint_paid": resp.hint_paid}
