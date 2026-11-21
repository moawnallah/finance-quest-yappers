"""Synthetic demo learners for the admin panel: python -m app.seed --synthetic 200.

Based on the router's test personas with random variation: surveys, attempts with scores, chosen
and finished paths, and a few tutor events. Every row belongs to a user with synthetic=True, so the
panel can label them ("Synthetic demo data") and exports leave them out unless asked."""
import random
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.engines import catalog
from app.insights_api import demo, onboarding_router
from app.models import Attempt, Event, LlmEvent, Onboarding, PathCheckin, RecoEvent, User

PERSONAS = [  # backend/ml/tests/test_router.py: YOUNG, INVESTOR, STUDENT, RETIREE
    {"age_band": "25-39", "goal": "first_investment", "horizon": "over_10", "self_rating": "quite_high", "buffer": "under_1",
     "products": ["life_insurance"], "know": 0.45, "experience": "none"},
    {"age_band": "25-39", "goal": "other", "horizon": "over_10", "self_rating": "very_high", "buffer": "6_plus",
     "products": ["investment", "life_insurance", "pension"], "know": 0.95, "experience": "quite_a_lot"},
    {"age_band": "18-24", "goal": "buffer", "horizon": "under_3", "self_rating": "quite_high", "buffer": "none",
     "products": ["consumer_loan"], "know": 0.25, "experience": "none"},
    {"age_band": "55+", "goal": "retirement", "horizon": "3_10", "self_rating": "average", "buffer": "3_6",
     "products": ["life_insurance", "non_life_insurance"], "know": 0.6, "experience": "a_little"},
]


def seed_synthetic(db: Session, n: int = 200, seed: int = 2026) -> int:
    rng = random.Random(seed)
    cat = catalog()
    now = datetime.now(timezone.utc)
    for i in range(n):
        p = dict(rng.choice(PERSONAS))
        if rng.random() < 0.3:
            p["goal"] = rng.choice(["buffer", "first_investment", "retirement", "home", "other"])
        if rng.random() < 0.3:
            p["horizon"] = rng.choice(["under_3", "3_10", "over_10"])
        know = min(0.98, max(0.05, p.pop("know") + rng.uniform(-0.2, 0.2)))
        survey = {**{k: p[k] for k in ("age_band", "goal", "horizon", "self_rating", "buffer", "products", "experience")},
                  "decisions": "me",
                  "knowledge": {q: {"correct": rng.random() < know, "confidence": rng.randint(1, 5)}
                                for q in ("Q2", "Q3", "Q4", "Q5", "Q6") if rng.random() < 0.9}}
        start = now - timedelta(days=rng.uniform(1, 30))
        u = User(id=str(uuid.uuid4()), token=secrets.token_urlsafe(32), display_name=f"Synthetic learner {i + 1}",
                 variant=rng.choice(["A", "B"]), created_at=start, synthetic=True, share_profile=True)
        db.add(u)
        db.flush()
        result = onboarding_router.route(survey, u.id)
        events = result.pop("events")
        result["demo"] = demo.match(result, set(cat.nodes))
        db.add(Onboarding(user_id=u.id, survey=survey, result=result, router_version=result["router_version"], created_at=start))
        for e in events:
            db.add(RecoEvent(user_id=u.id, ts=start, router_version=e["router_version"], event_type=e["event_type"],
                             node=e.get("node"), predicted_m=e.get("predicted_m"), need=e.get("need"), priority=e.get("priority"),
                             path=e.get("path")))
        path = [x["node"] for x in result["path"]]
        if rng.random() < 0.3 and result["demo"].get("options"):
            ch = rng.choice(result["demo"]["options"])["id"]
            path = demo.demo_paths()[ch]["nodes"]
            db.add(RecoEvent(user_id=u.id, ts=start, router_version=result["router_version"], event_type="path_chosen",
                             payload={"chosen": ch, "recommended": result["demo"].get("recommended")}))
        t = start
        live = [k for k in path if k in cat.nodes]
        reach = live[:rng.randint(0, len(live))]
        for k in reach:  # practice every scored item of the nodes this learner got to
            for item in [x for x in cat.nodes[k]["items"] if x["scored"]]:
                t += timedelta(minutes=rng.uniform(0.3, 4))
                ok = rng.random() < min(0.97, know + 0.25)
                db.add(Attempt(user_id=u.id, task_id=item["id"], node_id=k, level="easy", context="practice",
                               content_version=item.get("content_version", 1), response={"synthetic": True},
                               confidence=rng.randint(2, 5), score=1.0 if ok else 0.0, submitted_at=t,
                               duration_ms=rng.randint(5, 60)))
            db.add(Event(user_id=u.id, name="skill_opened", payload={"node_id": k}, created_at=t))
        if live and len(reach) == len(live) and rng.random() < 0.6:
            t += timedelta(minutes=5)
            goal = rng.choice(["keep_learning", "first_investment", "retirement", "buffer"])
            db.add(PathCheckin(user_id=u.id, path_id="recommended", ts=t,
                               answers={"progress": rng.choice(["yes", "yes", "somewhat", "no"]),
                                        "confidence": {k: rng.randint(2, 5) for k in live}, "next_goal": goal}))
            db.add(RecoEvent(user_id=u.id, ts=t, router_version=result["router_version"], event_type="path_finished",
                             payload={"path_id": "recommended", "next_goal": goal}))
            nxt = onboarding_router.next_steps(survey, result, set(reach), goal)
            if nxt:
                db.add(RecoEvent(user_id=u.id, ts=t, router_version=result["router_version"], event_type="next_steps_shown",
                                 path=[x["node"] for x in nxt], payload={"next_goal": goal}))
        for _ in range(rng.choice([0, 0, 1, 2, 3])):
            fb = rng.random() < 0.08
            db.add(LlmEvent(user_id=u.id, ts=t + timedelta(minutes=rng.uniform(0, 30)), mode="explain_concept", intent="question",
                            model_role="tutor_small", model="ollama/gemma4:12b", prompt_version="mo-v1",
                            node=rng.choice(path) if path else None, latency_ms=None if fb else rng.randint(2500, 14000),
                            checks_failed=["model_unreachable"] if fb else [], fallback_used=fb, flagged_for_review=False))
    db.commit()
    return n
