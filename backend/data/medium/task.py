"""One medium task: validate -> compile -> (question_view, reveal_view) -> score.

The compiled record has three blocks:
- question: safe to send before the answer (GET /tasks/{id})
- reveal:   only after the answer (POST /answers)
- meta:     internal (QA, data provenance)
"""
from __future__ import annotations

import datetime as dt

import re

from common import HINDSIGHT, AttemptError, check_source_ids, localize_all
from common import has_word as _has_word

from .parts import (RESPONSES, STIMULI, TRUTHS, Report, all_strings, as_date, is_text,
                    private_reasons, public_reasons, score_reasons, validate_reasons)
from .series import SeriesStore

VARIANTS = {"day_x", "estimate", "label"}
REVEAL_SHOW = {"truth", "outcome", "per_box_explain", "sources"}


def _kind(spec) -> str | None:
    """`truth: none` and `truth: {kind: none}` mean the same."""
    return spec if isinstance(spec, str) else spec.get("kind") if isinstance(spec, dict) else None


# ---------------------------------------------------------------- validate

def validate(task: dict, store: SeriesStore, today: dt.date | None = None,
             sources: dict | None = None) -> Report:
    r = Report()
    node = str(task.get("node", ""))
    tid = task.get("id")
    if not isinstance(tid, str) or not re.match(rf"^{re.escape(node.lower())}\.m[0-9]+$", tid):
        r.error(f"id {tid!r} must look like {node.lower()}.m<n> (the node id in lower case)")
    if task.get("level") != "medium":
        r.error("level must be medium")
    variant = task.get("variant")
    if variant not in VARIANTS:
        r.error(f"variant must be one of {sorted(VARIANTS)}")
    if not isinstance(task.get("content_version"), int) or task["content_version"] < 1:
        r.error("content_version must be a positive integer (bump it on any change that affects scoring)")
    if not task.get("author"):
        r.error("author is required")
    if not task.get("reviewer"):
        r.warn("no reviewer yet: the task must not go live")
    if "valid_until" in task:
        until = as_date(task["valid_until"])
        if until is None:
            r.error("valid_until must be a date")
        elif until < (today or dt.date.today()):
            r.error(f"valid_until {until} is in the past")
    if sources is None:
        if not isinstance(task.get("sources", []), list):
            r.error("sources must be a list of source ids")
    else:
        check_source_ids(str(tid), task.get("sources", []), sources, r)
    if not is_text(task.get("brief")):
        r.error("brief is required")
    if not is_text((task.get("reveal") or {}).get("text")):
        r.error("reveal.text is required")
    show = (task.get("reveal") or {}).get("show")
    if show is not None and (not isinstance(show, list) or not set(show) <= REVEAL_SHOW):
        r.error(f"reveal.show must be a list from {sorted(REVEAL_SHOW)}")

    stimuli = task.get("stimulus")
    if not isinstance(stimuli, list) or not stimuli:
        r.error("stimulus must be a non-empty list")
        stimuli = []
    for s in stimuli:
        kind = s.get("kind") if isinstance(s, dict) else None
        if kind not in STIMULI:
            r.error(f"stimulus kind {kind!r} not implemented ({sorted(STIMULI)})")
        else:
            STIMULI[kind].validate(s, store, r)
    has_chart = any(isinstance(s, dict) and s.get("kind") == "chart" for s in stimuli)
    if has_chart and _kind(stimuli[0]) != "chart":
        r.error("the chart the question is about must be the first stimulus")

    response = task.get("response") or {}
    if response.get("kind") not in RESPONSES:
        r.error(f"response kind {response.get('kind')!r} not implemented ({sorted(RESPONSES)})")
    else:
        RESPONSES[response["kind"]].validate(response, r)
        if response["kind"] == "direction" and not has_chart:
            r.error("a direction response needs a chart stimulus")

    truth = _kind(task.get("truth"))
    if truth not in TRUTHS:
        r.error(f"truth kind {truth!r} not implemented ({sorted(TRUTHS)})")
    if variant == "day_x" and truth != "none":
        r.error("day_x tasks have truth none (graded on reasons only)")
    if variant == "day_x" and not has_chart:
        r.error("day_x tasks need a chart with a cutoff")

    validate_reasons(task.get("reasons"), r)
    weights = task.get("weights") or {"estimate": 0.5, "reasons": 0.5}
    if truth != "none":
        try:
            if abs(weights["estimate"] + weights["reasons"] - 1) > 1e-9:
                r.error("weights.estimate + weights.reasons must equal 1")
        except (KeyError, TypeError):
            r.error("weights needs numbers estimate and reasons")

    if r.errors:  # the checks below assume a well-formed task
        return r
    visible = {"brief": task["brief"]}
    visible.update({f"reasons.{b['id']}": b["text"] for b in task["reasons"]["boxes"]})
    for o in response.get("options", []):
        if isinstance(o, dict):
            visible[f"response.{o.get('id')}"] = o.get("text")
    # Boxes with negative weight may be hindsight on purpose, so they skip the hindsight check.
    hindsight_ok = {f"reasons.{b['id']}" for b in task["reasons"]["boxes"] if b["weight"] < 0}
    # A task may also list fields where such a word states a fact known on day X, for example a
    # crash that had already happened: hindsight_ok: [brief, reasons.<id>, ...].
    hindsight_ok |= set(task.get("hindsight_ok") or [])
    hidden: list[str] = []
    for i, s in enumerate(stimuli):
        hidden += STIMULI[s["kind"]].hidden_words(s, store)
        for j, ser in enumerate(s.get("series", [])):
            if "label" in ser:
                visible[f"stimulus[{i}].series[{j}].label"] = ser["label"]
    for field, value in visible.items():
        for text in all_strings(value):
            for word in HINDSIGHT:
                if field not in hindsight_ok and _has_word(text, word):
                    r.error(f"{field}: hindsight word {word!r}")
            for word in hidden:
                if _has_word(text, word):
                    r.error(f"{field}: reveals the hidden name {word!r}")
    return r


# ---------------------------------------------------------------- compile

def compile_task(task: dict, store: SeriesStore, r: Report) -> dict | None:
    """Turn a validated task into the record the backend serves. Returns None on data errors."""
    ctx: dict = {}
    public_stimuli, private_stimuli = [], []
    for s in task["stimulus"]:
        pub, priv = STIMULI[s["kind"]].compile(s, store, r, ctx)
        public_stimuli.append(pub)
        private_stimuli.append(priv)

    response = task["response"]
    handler = RESPONSES[response["kind"]]
    outcome = handler.outcome(response, ctx, r)
    if r.errors:
        return None
    truth_kind = _kind(task["truth"])
    truth = TRUTHS[truth_kind].resolve(task["truth"], outcome)
    weights = task.get("weights") or {"estimate": 0.5, "reasons": 0.5}

    return {
        "id": task["id"],
        "node": task["node"],
        "level": "medium",
        "variant": task["variant"],
        "content_version": task["content_version"],
        "live": bool(task.get("reviewer")),
        "weights": {"estimate": 0.0, "reasons": 1.0} if truth_kind == "none" else weights,
        "question": {
            "brief": task["brief"],
            "stimulus": public_stimuli,
            "response": handler.public(response, ctx),
            "reasons": public_reasons(task["reasons"]),
            "confidence": {"min": 1, "max": 5},
        },
        "reveal": {
            "text": task["reveal"]["text"],
            "outcome": outcome,
            "truth": truth,
            "stimulus": private_stimuli,
            "reasons": private_reasons(task["reasons"]),
            "sources": task.get("sources", []),
            "show": task["reveal"].get("show") or sorted(REVEAL_SHOW),
        },
        "meta": {
            "content_file": task.get("_file"),
            "author": task.get("author"),
            "reviewer": task.get("reviewer"),
            "cutoff_used": ctx.get("cutoff_used"),
            "synthetic": ctx.get("synthetic", False),
            "attribution": ctx.get("attribution", []),
        },
    }


# ---------------------------------------------------------------- views

def question_view(record: dict, lang: str = "en") -> dict:
    """What GET /tasks/{id} returns: no truth, outcome, weights or explanations."""
    base = {k: record[k] for k in ("id", "node", "level", "variant", "content_version")}
    return {**base, **localize_all(record["question"], lang)}


def reveal_view(record: dict, lang: str = "en") -> dict:
    return localize_all(record["reveal"], lang)


# ---------------------------------------------------------------- score

def score(record: dict, response, reasons: list[str], confidence: int | None = None) -> dict:
    """Score one answer. Field names match the attempt record in docs/task_engines.md."""
    q = record["question"]
    err = RESPONSES[q["response"]["kind"]].check(q["response"], response)
    if err:
        raise AttemptError(err)
    box_ids = {b["id"] for b in q["reasons"]["boxes"]}
    picked = list(reasons)
    if len(set(picked)) != len(picked) or not set(picked) <= box_ids:
        raise AttemptError(f"reasons must be distinct ids from {sorted(box_ids)}")
    pick = q["reasons"]["pick"]
    if not pick["min"] <= len(picked) <= pick["max"]:
        raise AttemptError(f"pick {pick['min']}-{pick['max']} reasons")
    if confidence is not None and (isinstance(confidence, bool) or confidence not in range(1, 6)):
        raise AttemptError("confidence must be an integer from 1 to 5")

    truth = record["reveal"]["truth"]
    estimate = None if truth is None else RESPONSES[q["response"]["kind"]].score(q["response"], response, truth)
    reasons_score = score_reasons(record["reveal"]["reasons"], picked)
    w = record["weights"]
    total = reasons_score if estimate is None else w["estimate"] * estimate + w["reasons"] * reasons_score
    return {
        "task_id": record["id"],
        "content_version": record["content_version"],
        "level": "medium",
        "response": {"value": response, "reasons": picked},
        "confidence": confidence,
        "p": None if confidence is None else (confidence - 1) / 4,
        "score_estimate": estimate,
        "score_reasons": round(reasons_score, 4),
        "score": round(total, 4),
    }
