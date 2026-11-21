"""Who decides the learner's path: BASAL first, the rule router as the fallback.

BASAL_MODE=primary (with BASAL_URL set) asks BASAL, for each candidate node the router considered,
"should this learner study it now?" (start_p) and how sure it is (start_confidence). BASAL's path is
the nodes it says to study now, prerequisites first, then by how strongly it says so.

The router's path stays whenever BASAL cannot decide well: not configured, unreachable or slower
than the timeout, an error, too few confident answers (below TAU), or no node to study. Every call
returns a `decision` row saying who decided and why, logged as a reco_event of type path_decision.

BASAL_MODE=shadow (the default) keeps the old behaviour: the router decides, BASAL is only logged.
Nothing personal is sent to BASAL (bands, quiz answers and node titles; see router/shadow.py).
"""
from __future__ import annotations

import json
import os
import threading
from collections import OrderedDict

from router import shadow
from router.router import tree

MIN_CONFIDENT_SHARE = 0.5  # at least half of BASAL's start answers must be at or above TAU
_cache: OrderedDict[str, tuple[list, dict]] = OrderedDict()  # guests re-route on every path view
_lock = threading.Lock()


def mode() -> str:
    return "primary" if os.getenv("BASAL_MODE", "shadow").lower() == "primary" and shadow.url() else "shadow"


def _depth(node: str, t: dict, seen: frozenset = frozenset()) -> int:
    after = [a for a in t[node].get("after") or [] if a in t and a not in seen]
    return 0 if not after else 1 + max(_depth(a, t, seen | {node}) for a in after)


def basal_path(result: dict, decisions: list[dict], live: set[str] | None = None) -> list[dict]:
    """BASAL's path: the candidates it says to study now, prerequisites first, then by start_p.

    Guards keep it sensible: missions that exist come before planned ones when choosing, the router's
    first step stays (it answers the learner's goal, e.g. an emergency fund for a buffer goal), and a
    path shorter than three steps is topped up from the router's path."""
    t = tree()
    live = live if live is not None else set(t)
    by_router = {p["node"]: p for p in result["path"]}
    go = [d for d in decisions if (d.get("start_p") or 0) >= 0.5 and d["node"] in t]
    limit = max(3, len(result["path"]))
    go.sort(key=lambda d: (d["node"] not in live, -(d.get("start_p") or 0)))
    chosen = go[:limit]
    first = result["path"][0]["node"] if result["path"] else None
    if first and first not in {d["node"] for d in chosen}:
        chosen = chosen[: limit - 1] + [{"node": first, "start_p": None}]
    # A path of one or two steps is too thin: top it up from the router's path, in its order.
    for p in result["path"]:
        if len(chosen) >= min(3, len(result["path"])):
            break
        if p["node"] not in {d["node"] for d in chosen}:
            chosen.append({"node": p["node"], "start_p": None})
    # The router's first step answers the goal and leads (an emergency fund is step 1 for a buffer
    # goal, as in the router); the rest follow prerequisites first, then by start_p.
    head = [d for d in chosen if d["node"] == first]
    rest = sorted((d for d in chosen if d["node"] != first), key=lambda d: (_depth(d["node"], t), -(d.get("start_p") or 0)))
    chosen = head + rest
    out = []
    for d in chosen:
        k = d["node"]
        why = by_router.get(k, {}).get("reason")
        out.append({"node": k, "title": t[k]["title"],
                    "reason": why or f"Suggested for you now ({round(100 * d['start_p'])}% sure it fits)."})
    return out


def ensure_playable(result: dict, live: set[str], decisions: list[dict] | None = None) -> dict:
    """A path made only of planned (coming later) missions is a dead end: add the best playable one,
    by BASAL's start_p when there are answers, else by the router's priority; prerequisites stay first."""
    path = result["path"]
    if not path or any(p["node"] in live for p in path):
        return result
    t = tree()
    score = {d["node"]: d.get("start_p") or 0 for d in decisions or []}
    pool = [k for k in result.get("priority", {}) if k in live and k in t and k not in {p["node"] for p in path}]
    if not pool:
        return result
    best = max(pool, key=lambda k: (score.get(k, 0), result["priority"].get(k, 0)))
    extra = {"node": best, "title": t[best]["title"], "reason": "Something you can start now while the rest is being written."}
    rest = sorted(path[1:] + [extra], key=lambda p: _depth(p["node"], t))  # the goal step keeps its place
    return {**result, "path": [path[0]] + rest}


def decide(survey: dict, result: dict) -> tuple[dict, dict]:
    """Return (result with the chosen path, decision row). Never raises; the router is the fallback."""
    from app.engines import catalog  # here, not at import time: app.engines loads the content
    live = set(catalog().nodes)
    result, row = _decide(survey, result, live)
    return ensure_playable(result, live, row.get("decisions")), row


def _decide(survey: dict, result: dict, live: set[str]) -> tuple[dict, dict]:
    row: dict = {"mode": mode(), "decided_by": "rules"}
    if row["mode"] != "primary":
        return result, row
    key = json.dumps(survey, sort_keys=True, default=str)
    with _lock:
        hit = _cache.get(key)
    if hit is None:
        try:
            response, latency = shadow.ask(shadow.build_request(survey, result), shadow.url())
            decisions = shadow.compare(result, response)
            hit = (decisions, {"model": response.get("model"), "latency_ms": latency})
        except Exception as e:  # noqa: BLE001 - BASAL failing must never break onboarding
            row.update(fallback="unreachable", error=f"{type(e).__name__}: {e}"[:200])
            return result, row
        with _lock:
            _cache[key] = hit
            while len(_cache) > 500:
                _cache.popitem(last=False)
    decisions, meta = hit
    row.update(meta, tau=shadow.TAU, decisions=decisions)
    answered = [d for d in decisions if d.get("start_p") is not None]
    confident = [d for d in answered if not d.get("below_tau")]
    if not answered or len(confident) / len(answered) < MIN_CONFIDENT_SHARE:
        row["fallback"] = "low_confidence"
        return result, row
    path = basal_path(result, decisions, live)
    if not path:
        row["fallback"] = "no_node_to_study"
        return result, row
    row.update(decided_by="basal", router_path=[p["node"] for p in result["path"]], path=[p["node"] for p in path])
    return {**result, "path": path, "decided_by": "basal", "router_path": result["path"]}, row
