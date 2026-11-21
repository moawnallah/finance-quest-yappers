"""The onboarding router (docs/onboarding_router.md): survey -> knowledge score, benchmarks,
node mastery, needs, priority, first path, challenges, and reco_events rows; and, when a path is
finished, the next nodes to study (next_steps).

No trained model: a Rasch ability from the EB525 knowledge items the user answered, with the same
prior for everyone, explicit need rules, and the priority formula. Deterministic. A typed decision
model can be asked in shadow mode next to it (router/shadow.py); it never changes the path.
"""
from __future__ import annotations

import datetime as dt
import math
import uuid
from functools import lru_cache
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROUTER_VERSION = "rules-2"  # 2026-11-21: paths of 3+ nodes, goal "buffer", experience, unasked items left out

# Item difficulties solved so that mean P(correct) over theta ~ N(0,1) equals the Polish share.
ITEM_B = {"Q2": 0.67, "Q3": -0.91, "Q4": 1.54, "Q5": -0.33, "Q6": -0.17}
ITEM_NODE = {"Q2": "F3", "Q3": "F2", "Q4": "I3", "Q5": "I1", "Q6": "P1"}
ITEM_TOPIC = {"Q2": "compound interest", "Q3": "inflation", "Q4": "bond prices", "Q5": "risk and return",
              "Q6": "diversification"}
LEVEL_D = {"E": -0.5, "M": 0.5, "H": 1.5}
KNOWN, UNMET, WEAK = 0.8, 0.6, 0.4   # mastery thresholds: probably known / prerequisite met / full node
GAMMA, BASE_NEED, MIN_PATH, MAX_PATH, TARGETS = 0.3, 0.2, 3, 5, 2
NEXT_STEPS = 3  # nodes suggested when a path is finished
GRID = [i / 40 for i in range(-200, 201)]  # theta from -5 to 5


@lru_cache(maxsize=1)
def tree() -> dict[str, dict]:
    return yaml.safe_load((HERE / "tree.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def benchmarks() -> dict:
    return yaml.safe_load((HERE / "benchmarks.yaml").read_text(encoding="utf-8"))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _depth(node: str) -> int:
    after = tree()[node]["after"]
    return 0 if not after else 1 + max(_depth(a) for a in after)


def _ancestors(node: str) -> set[str]:
    out: set[str] = set()
    for a in tree()[node]["after"]:
        out |= {a} | _ancestors(a)
    return out


# ---------------------------------------------------------------- knowledge

def _correct(survey: dict) -> dict[str, int]:
    """Answered items only: 1 = correct, 0 = wrong or "don't know" (as in the EB525 report).
    An item that was not asked (the quick check was skipped) is left out: it is no evidence either way."""
    knowledge = survey.get("knowledge") or {}
    return {q: 1 if (knowledge.get(q) or {}).get("correct") is True else 0 for q in ITEM_B if q in knowledge}


def _band(score: int | None) -> str | None:
    return None if score is None else "low" if score <= 1 else "medium" if score <= 3 else "high"


def ability(correct: dict[str, int]) -> float:
    """EAP of theta on a grid with prior N(0, 1) and the Rasch likelihood."""
    weights = []
    for t in GRID:
        w = math.exp(-t * t / 2)
        for q, x in correct.items():
            p = _sigmoid(t - ITEM_B[q])
            w *= p if x else 1 - p
        weights.append(w)
    total = sum(weights)
    return sum(t * w for t, w in zip(GRID, weights)) / total


def mastery(theta: float, correct: dict[str, int]) -> dict[str, float]:
    theta_k = {k: theta for k in tree()}
    for q, x in correct.items():
        theta_k[ITEM_NODE[q]] = theta + 0.5 * (x - _sigmoid(theta - ITEM_B[q]))
    return {k: _sigmoid(theta_k[k] - LEVEL_D[n["level"]]) for k, n in tree().items()}


# ---------------------------------------------------------------- needs

def needs(survey: dict, score: int | None) -> tuple[dict[str, float], dict[str, str]]:
    """Need per node (base 0.2, max over the rules that fire) and the reason of the strongest rule."""
    n = {k: BASE_NEED for k in tree()}
    why: dict[str, str] = {}

    def rule(nodes_values: dict[str, float], reason: str):
        for node, v in nodes_values.items():
            if v > n[node]:
                n[node], why[node] = v, reason

    age, products, buffer = survey.get("age_band"), survey.get("products"), survey.get("buffer")
    goal, horizon = survey.get("goal"), survey.get("horizon")
    if goal == "buffer":
        rule({"S1": 0.9}, "Your goal is an emergency buffer.")
    if buffer in ("none", "under_1"):
        rule({"S1": 1.0}, "You said you could not cover a month of costs without income.")
    elif buffer == "1_3":
        rule({"S1": 0.6}, "Your safety buffer covers less than 3 months.")
    if products is not None:
        if "consumer_loan" in products:
            rule({"F4": 0.8, "S2": 0.8}, "You have a consumer loan.")
        if "mortgage" in products:
            rule({"L2": 0.8}, "You have a mortgage.")
        if "investment" in products:
            rule({"I4": 0.7, "I5": 0.7, "P1": 0.7}, "You already hold investments.")
        elif goal == "first_investment":
            rule({"I1": 0.8, "I2": 0.7, "P1": 0.6}, "You want to start investing.")
        if "crypto" in products:
            rule({"D4": 0.8, "I7": 0.6, "O1": 0.6}, "You hold crypto.")
        if "pension" not in products and age in ("25-39", "40-54"):
            rule({"L1": 0.6}, "You have no private pension product yet.")
    elif goal == "first_investment":
        rule({"I1": 0.8, "I2": 0.7, "P1": 0.6}, "You want to start investing.")
    if survey.get("experience") in ("a_little", "quite_a_lot") and "investment" not in (products or []):
        rule({"I4": 0.7, "I5": 0.7, "P1": 0.7}, "You have invested before.")
    if goal == "retirement":
        rule({"L1": 0.9}, "Your goal is retirement.")
    if age == "55+":
        rule({"L3": 0.8, "O1": 0.8}, "These matter most when retirement is close.")
    if age in ("18-24", "under_18"):
        rule({"F1": 0.6, "F4": 0.6, "O1": 0.6}, "Most useful at the start of your own budget.")
    if horizon == "under_3":
        rule({"S4": 0.7, "I2": 0.7}, "Your goal is less than 3 years away.")
    if survey.get("decisions") == "someone_else":
        rule({"F1": 0.6}, "Someone else manages the money at home; this gives you the basics.")
    if survey.get("self_rating") in ("very_high", "quite_high") and score is not None and score <= 2:
        rule({"D4": 0.8}, "You rated your knowledge high, but the quiz showed gaps.")
    return n, why


# ---------------------------------------------------------------- path

def route(survey: dict, user_pseudo_id: str = "anonymous") -> dict:
    t = tree()
    correct = _correct(survey)
    score = sum(correct.values()) if len(correct) == len(ITEM_B) else None  # the EB525 score needs all 5 items
    theta = ability(correct)
    m = mastery(theta, correct)
    n, why = needs(survey, score)

    over: dict[str, float] = {}
    over_why: dict[str, str] = {}
    for q, x in correct.items():
        conf = (survey.get("knowledge", {}).get(q) or {}).get("confidence")
        if conf and not x:
            node = ITEM_NODE[q]
            over[node] = GAMMA * (conf - 1) / 4
            over_why[node] = f"You were sure about the {ITEM_TOPIC[q]} question, but the answer was wrong."
    priority = {k: n[k] * (1 - m[k]) + over.get(k, 0.0) for k in t}

    def reason(k: str) -> str:
        need_term = n[k] * (1 - m[k])
        if over.get(k, 0) > need_term and k in over_why:
            return over_why[k]
        return why.get(k) or over_why.get(k) or "Recommended for your level."

    known = {k for k in t if m[k] >= KNOWN}
    order = list(t)
    pool = sorted((k for k in t if k not in known and t[k]["level"] != "H"),
                  key=lambda k: (-round(priority[k], 6), order.index(k)))
    targets = pool[:TARGETS]

    path: dict[str, str] = {}
    challenges: dict[str, str] = {}

    def add(k: str, why_text: str):
        if k in path:
            return
        path[k] = why_text
        for a in t[k]["after"]:
            if m[a] < WEAK:
                add(a, f"Needed before {t[k]['title']}.")
            elif m[a] < UNMET or a in known:
                challenges.setdefault(a, f"Before {t[k]['title']}: a 2-question challenge to check you know it.")

    if n["S1"] >= 0.6 and "S1" not in known:
        add("S1", reason("S1"))
    for k in targets:
        add(k, reason(k))
    for k in pool[TARGETS:]:  # 2 nodes are too short for a path: add the next targets until there are MIN_PATH
        if len(path) >= MIN_PATH:
            break
        add(k, reason(k))
    for k in list(path):  # probably-known ancestors of the path are offered as challenges
        for a in _ancestors(k):
            if a in known and a not in path:
                challenges.setdefault(a, "Probably known: take the 2-question challenge to skip it.")
    for k in path:
        challenges.pop(k, None)

    ranked = sorted(path, key=lambda k: (k != "S1", _depth(k), order.index(k)))[:MAX_PATH]
    goal_candidates = sorted((k for k in t if k not in known), key=lambda k: (-priority[k], order.index(k)))
    goal = next((k for k in goal_candidates if k not in ranked), None) if goal_candidates else None
    goal = goal if goal and priority[goal] > max((priority[k] for k in ranked), default=0) else None

    result = {
        "router_version": ROUTER_VERSION,
        "knowledge_score": score,
        "items_answered": len(correct),
        "band": _band(score),
        "benchmarks": _benchmarks(survey, score),
        "theta": round(theta, 3),
        "mastery": {k: round(v, 3) for k, v in m.items()},
        "needs": n,
        "priority": {k: round(v, 3) for k, v in priority.items()},
        "path": [{"node": k, "title": t[k]["title"], "reason": path[k]} for k in ranked],
        "challenges": [{"node": k, "title": t[k]["title"], "why": w} for k, w in
                       sorted(challenges.items(), key=lambda kv: (_depth(kv[0]), order.index(kv[0])))],
        "goal": {"node": goal, "title": t[goal]["title"], "reason": reason(goal)} if goal else None,
    }
    result["events"] = _events(result, n, over, user_pseudo_id)
    return result


# ---------------------------------------------------------------- after a finished path

GOALS = {"buffer", "first_investment", "retirement", "home", "other"}


def next_steps(survey: dict, result: dict, done: set[str], next_goal: str | None = None, k: int = NEXT_STEPS) -> list[dict]:
    """The nodes to study after a finished path, best first.

    Needs are recomputed with the goal from the end-of-path check-in (keep_learning keeps the
    survey's goal); done nodes count as known, and nodes probably known at the survey are skipped.
    Order:
    1. nodes a need rule asks for, by priority. When such a node is not open yet (a prerequisite is
       neither done nor met at the survey, mastery < UNMET), its first missing prerequisite is
       suggested instead, "needed before" it;
    2. nodes that build on a done node, easier levels first;
    3. the rest, easier levels first."""
    t, order = tree(), list(tree())
    goal = next_goal if next_goal in GOALS else survey.get("goal")
    n, why = needs({**survey, "goal": goal}, result.get("knowledge_score"))
    m = {**result["mastery"], **{d: 1.0 for d in done}}
    todo = [x for x in t if x not in done and m[x] < KNOWN]
    pri = {x: n[x] * (1 - m[x]) for x in todo}

    def missing(x: str) -> list[str]:
        return [a for a in t[x]["after"] if a not in done and m[a] < UNMET]

    def entry(x: str) -> str:  # the first node to study on the way to x
        gaps = missing(x)
        return x if not gaps else entry(gaps[0])

    def tier(x: str) -> int:
        return 0 if n[x] > BASE_NEED else 1 if any(a in done for a in t[x]["after"]) else 2

    level = {"E": 0, "M": 1, "H": 2}
    out: dict[str, str] = {}
    for x in sorted(todo, key=lambda x: (tier(x), level[t[x]["level"]] if tier(x) else 0, -pri[x], order.index(x))):
        e = entry(x)
        if e in out or e in done:
            continue
        built = [a for a in t[e]["after"] if a in done]
        out[e] = (why[x] if e == x and tier(x) == 0 else f"Needed before {t[x]['title']}." if e != x
                  else f"It builds on {t[built[0]]['title']}, which you have finished." if built
                  else "Recommended for your level.")
        if len(out) == k:
            break
    return [{"node": x, "title": t[x]["title"], "reason": r} for x, r in out.items()]


# ---------------------------------------------------------------- benchmarks and events

def _benchmarks(survey: dict, score: int | None) -> dict:
    b = benchmarks()
    group = survey.get("age_band") if survey.get("age_band") in b["groups"] else "18-24" \
        if survey.get("age_band") == "under_18" else None
    band = _band(score)
    out = {"source": b["source"], "group": group,
           "your_band_share": None if band is None else {"poland": b["knowledge_band"][band]["all"],
                                                         "your_age": b["knowledge_band"][band].get(group) if group else None},
           "items": {q: {"you": bool(x), "poland": b["items_correct"][q]["all"],
                         "your_age": b["items_correct"][q].get(group) if group else None}
                     for q, x in _correct(survey).items()}}
    if group:
        out["self_rating_high_your_age"] = b["self_rating_high"][group]
        out["buffer_under_one_month_your_age"] = b["buffer_under_one_month"][group]
    return out


def _events(result: dict, n: dict, over: dict, user: str) -> list[dict]:
    """reco_events rows (docs/tutor_agent.md, section 6): one path_issued, one recommendation_shown
    per path node and one per challenge."""
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    base = {"ts": ts, "user_pseudo_id": user, "router_version": ROUTER_VERSION}
    rows = [{**base, "event_id": str(uuid.uuid4()), "event_type": "path_issued",
             "path": [p["node"] for p in result["path"]]}]
    for kind, items in (("recommendation_shown", result["path"]), ("challenge_offered", result["challenges"])):
        for it in items:
            k = it["node"]
            rows.append({**base, "event_id": str(uuid.uuid4()), "event_type": kind, "node": k,
                         "predicted_m": result["mastery"][k], "need": n[k], "overconfidence_term": round(over.get(k, 0.0), 3),
                         "priority": result["priority"][k], "reason_term": it.get("reason") or it.get("why")})
    return rows
