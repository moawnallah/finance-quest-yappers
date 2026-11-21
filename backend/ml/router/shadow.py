"""Shadow decisions from a typed decision model (BASAL, POST /v1/systemone) next to the rule router
(docs/onboarding_router.md, "Shadow decision model: BASAL").

Reader: whoever runs the BASAL comparison. The router decides every path; this module only asks the
model the same two questions per candidate node and returns rows to log as reco_events of type
`shadow_decision`. Nothing here changes what a user sees.

Off unless BASAL_URL is set (for example http://gpu-box:8000). No personal data is sent: bands,
quiz answers and node titles only, the same rule as for the tutor.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

from .router import ITEM_TOPIC, tree

TAU = 0.7          # below this confidence the algorithm would decide (fitted on data later)
CANDIDATES = 8     # path nodes first, then the highest-priority others
TIMEOUT_S = 3.0    # the onboarding reply must not wait longer than this for a shadow answer


def url() -> str | None:
    return os.getenv("BASAL_URL") or None


def candidates(result: dict) -> list[str]:
    path = [p["node"] for p in result["path"]]
    rest = sorted((k for k in result["priority"] if k not in path), key=lambda k: -result["priority"][k])
    return (path + rest)[:CANDIDATES]


def build_request(survey: dict, result: dict, with_router: bool = True) -> dict:
    """with_router=False leaves the router's mastery out of the state: does the model add anything alone?"""
    t = tree()
    knowledge = survey.get("knowledge") or {}
    state = {
        "age_band": survey.get("age_band"), "goal": survey.get("goal"), "horizon": survey.get("horizon"),
        "experience": survey.get("experience"), "buffer_months": survey.get("buffer"),
        "products": survey.get("products"), "self_rating": survey.get("self_rating"),
        "quiz": {ITEM_TOPIC[q]: ("correct" if a.get("correct") is True else "don't know" if a.get("correct") is None else "wrong")
                 for q, a in knowledge.items() if q in ITEM_TOPIC},
        "candidates": [{"node": k, "title": t[k]["title"], "level": t[k]["level"],
                        "prerequisites": [t[a]["title"] for a in t[k]["after"]],
                        **({"router_mastery": result["mastery"][k]} if with_router else {})}
                       for k in candidates(result)],
    }
    questions = {}
    for k in candidates(result):
        title = t[k]["title"]
        questions[f"ready_{k}"] = {"type": "noul", "instructions":
                                   f"Will this learner answer the first check question of '{title}' correctly?"}
        questions[f"start_{k}"] = {"type": "noul", "instructions":
                                   f"Should this learner study '{title}' now, given the goal and the gaps?"}
    return {"state": state, "questions": questions, "lang": "en"}


def ask(request: dict, base_url: str, timeout: float = TIMEOUT_S) -> tuple[dict, int]:
    """POST the request; returns (response, latency in ms). Raises on any error: the caller logs it."""
    req = urllib.request.Request(base_url.rstrip("/") + "/v1/systemone", data=json.dumps(request).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    return body, int((time.monotonic() - t0) * 1000)


def compare(result: dict, response: dict, tau: float = TAU) -> list[dict]:
    """One row per candidate: the router's mastery and path membership next to the model's answers."""
    path = {p["node"] for p in result["path"]}
    answers = response.get("answers") or {}
    rows = []
    for k in {q.split("_", 1)[1] for q in answers}:
        ready, start = answers.get(f"ready_{k}") or {}, answers.get(f"start_{k}") or {}
        rows.append({"node": k, "router_m": result["mastery"].get(k), "on_path": k in path,
                     "ready_p": ready.get("noul"), "start_p": start.get("noul"),
                     "start_confidence": start.get("confidence"),
                     "agrees": None if start.get("noul") is None else (start["noul"] >= 0.5) == (k in path),
                     "below_tau": (start.get("confidence") or 0) < tau})
    return sorted(rows, key=lambda r: r["node"])


def shadow(survey: dict, result: dict) -> dict | None:
    """The payload of one shadow_decision row, or None when BASAL_URL is not set. Never raises."""
    base = url()
    if not base:
        return None
    try:
        response, latency = ask(build_request(survey, result), base)
        return {"model": response.get("model"), "latency_ms": latency, "tau": TAU,
                "decisions": compare(result, response)}
    except Exception as e:  # noqa: BLE001 - a shadow failure must never break onboarding
        return {"error": f"{type(e).__name__}: {e}"[:200]}
