"""Onboarding, profile, feedback, study mode and the admin views (docs/admin_and_profile.md).

The numbers come from backend/ml/analytics (pure functions with tests); this module only reads rows,
calls them and stores what users send. Admin routes need the admin key in the X-Admin-Key header.
"""
import random
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import AB_VARIANTS, BACKEND_DIR
from app.db import get_db
from app.deps import ApiError, current_user, log_event, require_admin, require_study_access
from app.engines import catalog, node_status
from app.models import (Attempt, BenchmarkAnswer, Consent, Event, Feedback, LlmEvent, Onboarding, PathCheckin, Profile,
                        RecoEvent, User)

ML_DIR = BACKEND_DIR / "ml"
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import analytics  # noqa: E402
import router as onboarding_router  # noqa: E402
from router import demo  # noqa: E402
from tutor.rules import mask  # noqa: E402

router = APIRouter(tags=["insights"])
admin = [Depends(require_admin)]


# ---------------------------------------------------------------- helpers

ATTEMPT_FIELDS = ("id", "user_id", "task_id", "node_id", "level", "context", "response", "confidence", "p", "score",
                  "accepted", "started_at", "submitted_at", "hints_used", "clarity_rating", "points", "growth_index",
                  "duration_ms", "failed_test")


def _rows(attempts) -> list[dict]:
    return [{f: getattr(a, f) for f in ATTEMPT_FIELDS} for a in attempts]


def _attempts(db: Session, user_id: str | None = None) -> list[Attempt]:
    q = select(Attempt).order_by(Attempt.id)
    if user_id:
        q = q.where(Attempt.user_id == user_id)
    return list(db.scalars(q))


def _llm_rows(db: Session) -> list[dict]:
    """Mo's llm_events rows as dicts for analytics.tutor_overview (no text)."""
    return [{"ts": e.ts, "intent": e.intent, "checks_failed": e.checks_failed or [], "fallback_used": e.fallback_used,
             "flagged_for_review": e.flagged_for_review, "latency_ms": e.latency_ms, "model": e.model}
            for e in db.scalars(select(LlmEvent))]


def _reports(db: Session) -> list[dict]:
    return [{"target_id": f.target_id, "kind": f.kind, "status": f.status} for f in db.scalars(select(Feedback))]


# ---------------------------------------------------------------- onboarding and profile

class KnowledgeItem(BaseModel):
    """One knowledge question: right, wrong or don't know (null), and how sure (1-5)."""
    model_config = ConfigDict(strict=True)  # "yes" or "4" are errors, not quietly converted
    correct: bool | None = None
    confidence: int | None = Field(default=None, ge=1, le=5)


class SurveyIn(BaseModel):
    """The 12 survey answers (docs/onboarding_router.md, "Implementation")."""
    age_band: Literal["under_18", "18-24", "25-39", "40-54", "55+"]
    decisions: Literal["me", "with_someone", "someone_else"] | None = None
    goal: Literal["buffer", "first_investment", "retirement", "home", "other"]
    horizon: Literal["under_3", "3_10", "over_10"]
    self_rating: Literal["very_high", "quite_high", "average", "quite_low", "very_low", "dont_know"] | None = None
    knowledge: dict[Literal["Q2", "Q3", "Q4", "Q5", "Q6"], "KnowledgeItem"] = Field(
        description='Per item {"correct": true | false | null (don\'t know), "confidence": 1-5}.')
    buffer: Literal["none", "under_1", "1_3", "3_6", "6_plus"] | None = None
    products: list[Literal["pension", "life_insurance", "non_life_insurance", "mortgage", "consumer_loan",
                           "investment", "crypto", "none"]] | None = None


@router.post("/onboarding")
def onboarding(body: SurveyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Score the survey, place the user in the tree, store the result and the router's events."""
    survey = body.model_dump()
    if survey["age_band"] == "under_18":  # no buffer or product questions for minors
        survey["buffer"], survey["products"] = None, None
    result = onboarding_router.route(survey, user.id)
    events = result.pop("events")
    result["demo"] = demo.match(result, set(catalog().nodes))
    row = db.get(Onboarding, user.id) or Onboarding(user_id=user.id)
    row.survey, row.result, row.router_version = survey, result, result["router_version"]
    row.created_at = datetime.now(timezone.utc)
    db.add(row)
    for e in events:  # Mo's reco_events columns (app/models.py); the reason text goes in reason_term
        db.add(RecoEvent(user_id=user.id, router_version=e["router_version"], event_type=e["event_type"],
                         node=e.get("node"), predicted_m=e.get("predicted_m"), need=e.get("need"),
                         overconfidence_term=e.get("overconfidence_term"), priority=e.get("priority"),
                         reason_term=(e.get("reason_term") or "")[:200] or None, path=e.get("path")))
    db.add(RecoEvent(user_id=user.id, router_version=result["router_version"], event_type="demo_match",
                     payload={"status": result["demo"]["status"], "path_id": result["demo"]["path_id"],
                              "recommended": result["demo"]["recommended"]}))
    log_event(db, user, "onboarding_done", path=[p["node"] for p in result["path"]])
    db.commit()
    return {k: result[k] for k in ("router_version", "knowledge_score", "band", "benchmarks", "path", "challenges", "goal",
                                   "demo")}


class ChoosePathIn(BaseModel):
    path_id: str = Field(description="One of the demo paths offered in the onboarding reply (demo.options[].id).")


@router.post("/onboarding/choose-path")
def choose_path(body: ChoosePathIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The user's pick when the recommended path is not ready, or a switch to the other demo path.
    Logged with the recommended path: a label for the next-step model."""
    onb = db.get(Onboarding, user.id)
    if not onb:
        raise ApiError(409, "no_onboarding", "Send the survey first (POST /onboarding)")
    if body.path_id not in demo.demo_paths():
        raise ApiError(400, "invalid_request", f"path_id must be one of {sorted(demo.demo_paths())}")
    result = dict(onb.result)
    result["chosen_path"] = body.path_id
    onb.result = result
    db.add(RecoEvent(user_id=user.id, router_version=onb.router_version, event_type="path_chosen", node=None,
                     payload={"chosen": body.path_id, "recommended": result["demo"]["recommended"],
                              "status": result["demo"]["status"], "closest": result["demo"].get("closest")}))
    db.commit()
    p = demo.demo_paths()[body.path_id]
    return {"path_id": body.path_id, "title": p["title"], "nodes": p["nodes"], "challenges": demo._challenges(p["nodes"])}


class PathFinishIn(BaseModel):
    """The end-of-path check-in (about 30 seconds)."""
    path_id: str
    progress: Literal["yes", "somewhat", "no"] = Field(description="Do you think you made progress?")
    confidence: dict[str, int] = Field(default_factory=dict, description="Confidence 1-5 per area of the path, e.g. {'S1': 4}.")
    next_goal: Literal["buffer", "first_investment", "retirement", "home", "keep_learning", "other"]


@router.post("/paths/finish")
def finish_path(body: PathFinishIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Store the check-in and return the thanks screen: the demo note, the optional feedback ask, the other path."""
    if body.path_id not in demo.demo_paths() and body.path_id != "personal":
        raise ApiError(400, "invalid_request", f"path_id must be 'personal' or one of {sorted(demo.demo_paths())}")
    if any(not 1 <= v <= 5 for v in body.confidence.values()):
        raise ApiError(400, "invalid_request", "confidence values must be 1-5")
    db.add(PathCheckin(user_id=user.id, path_id=body.path_id, answers=body.model_dump(exclude={"path_id"})))
    db.add(RecoEvent(user_id=user.id, router_version=onboarding_router.ROUTER_VERSION, event_type="path_finished",
                     payload={"path_id": body.path_id, "progress": body.progress, "next_goal": body.next_goal}))
    log_event(db, user, "path_finished", path_id=body.path_id)
    db.commit()
    return demo.finished(body.path_id)


@router.get("/me/summary")
def my_summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The profile: path, goal, progress per panel, how sure vs how right, hard results, activity."""
    cat = catalog()
    attempts = _attempts(db, user.id)
    by_node: dict[str, list[Attempt]] = {}
    for a in attempts:
        by_node.setdefault(a.node_id, []).append(a)
    states = {n: node_status(cat, n, user.id, by_node.get(n, [])) for n in cat.nodes}
    onb = db.get(Onboarding, user.id)
    return analytics.profile_summary(_rows(attempts), onboarding_router.tree(), states, onb.result if onb else None)


@router.get("/roadmap")
def roadmap():
    """Every node of the skills tree, built or planned. `live` is false for nodes without content yet,
    so the app can draw planned topics in their own colour ("coming later")."""
    cat, t = catalog(), onboarding_router.tree()
    return {"nodes": [{"id": k, "title": v["title"], "panel": v["panel"], "level": v["level"], "after": v["after"],
                       "live": k in cat.nodes} for k, v in t.items()]}


@router.get("/me/path")
def my_path(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The recommended learning path from the starting survey (POST /onboarding): the steps to follow in
    order, each with its title, why it is there, whether it has content yet, and the learner's progress.
    `steps` is what to show: the chosen demo path, the ready demo path, or the router's recommendation."""
    onb = db.get(Onboarding, user.id)
    if not onb:
        return {"survey_done": False, "steps": [], "challenges": []}
    cat, t = catalog(), onboarding_router.tree()
    res = onb.result
    reasons = {p["node"]: p.get("reason") for p in res.get("path", [])}
    demo_block = res.get("demo") or {}
    chosen = res.get("chosen_path")
    if chosen and chosen in demo.demo_paths():
        ids, source = demo.demo_paths()[chosen]["nodes"], "chosen"
    elif demo_block.get("status") == "ready" and demo_block.get("path"):
        ids, source = demo_block["path"], "demo" if demo_block.get("path_id") != "personal" else "personal"
    else:
        ids, source = [p["node"] for p in res.get("path", [])], "recommended"
    attempts = _attempts(db, user.id)
    by_node: dict[str, list[Attempt]] = {}
    for a in attempts:
        by_node.setdefault(a.node_id, []).append(a)
    steps = []
    for k in ids:
        live = k in cat.nodes
        st = node_status(cat, k, user.id, by_node.get(k, [])) if live else None
        steps.append({"node": k, "title": t.get(k, {}).get("title", k), "panel": t.get(k, {}).get("panel"),
                      "level": t.get(k, {}).get("level"), "reason": reasons.get(k), "live": live,
                      "done": bool(st and st.get("done")), "answered": (st or {}).get("items_answered", 0),
                      "total": (st or {}).get("items_total", 0)})
    nxt = next((x["node"] for x in steps if x["live"] and not x["done"]), None)
    return {"survey_done": True, "source": source, "goal": res.get("goal"), "band": res.get("band"),
            "knowledge_score": res.get("knowledge_score"), "steps": steps, "next": nxt,
            "challenges": [{"node": c["node"], "title": c.get("title"), "why": c.get("why"), "live": c["node"] in cat.nodes}
                           for c in res.get("challenges", [])],
            "demo": {k: demo_block.get(k) for k in ("status", "path_id", "message", "closest")},
            "options": [{"id": o["id"], "title": o["title"], "for": o.get("for"), "nodes": o["nodes"]}
                        for o in demo_block.get("options", [])],
            "recommended": [p["node"] for p in res.get("path", [])], "created_at": onb.created_at.isoformat()}


class NodeOpenedIn(BaseModel):
    node: str = Field(max_length=10)
    source: Literal["recommended", "self_chosen", "explore_wheel", "tutor_link", "end_of_path"]


@router.post("/events/node-opened")
def node_opened(body: NodeOpenedIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Log which node the user opened and from where. Self-chosen clicks feed the next-step model."""
    if body.node not in onboarding_router.tree():
        raise ApiError(404, "not_found", f"No node {body.node}")
    log_event(db, user, "node_opened", node=body.node, source=body.source)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- feedback

class FeedbackIn(BaseModel):
    where: Literal["item", "card", "task", "tutor_answer", "screen", "mission"]
    target_id: str = Field(max_length=60)
    kind: Literal["wrong_fact", "unclear", "bug", "idea", "other", "rating"]
    rating: int | None = Field(default=None, ge=1, le=5)
    text: str | None = Field(default=None, max_length=500)


@router.post("/feedback")
def send_feedback(body: FeedbackIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """'Report a problem' on an item, card, task or tutor answer, or a 1-5 rating after a mission."""
    if body.kind == "rating" and body.rating is None:
        raise ApiError(400, "invalid_request", "a rating needs 'rating' 1-5")
    fb = Feedback(user_id=user.id, where=body.where, target_id=body.target_id, kind=body.kind, rating=body.rating,
                  text=mask(body.text) if body.text else None)
    db.add(fb)
    db.commit()
    return {"id": fb.id, "status": fb.status}


@router.get("/admin/feedback", dependencies=admin)
def list_feedback(status: str | None = None, db: Session = Depends(get_db)):
    q = select(Feedback).order_by(Feedback.id.desc())
    if status:
        q = q.where(Feedback.status == status)
    rows = [{"id": f.id, "ts": f.ts.isoformat(), "where": f.where, "target_id": f.target_id, "kind": f.kind,
             "rating": f.rating, "text": f.text, "status": f.status} for f in db.scalars(q)]
    return {"alerts": analytics.report_alerts(_reports(db)), "reports": rows}


class FeedbackStatusIn(BaseModel):
    status: Literal["new", "triaged", "fixed", "wont_fix"]


@router.patch("/admin/feedback/{feedback_id}", dependencies=admin)
def update_feedback(feedback_id: int, body: FeedbackStatusIn, db: Session = Depends(get_db)):
    fb = db.get(Feedback, feedback_id)
    if not fb:
        raise ApiError(404, "not_found", f"No report {feedback_id}")
    before = fb.status
    fb.status = body.status
    fb.resolved_at = datetime.now(timezone.utc) if body.status in ("fixed", "wont_fix") else None
    log_event(db, None, "admin_feedback_status", feedback_id=feedback_id, before=before, after=body.status)
    db.commit()
    return {"id": fb.id, "status": fb.status}


# ---------------------------------------------------------------- study mode (hallway test)

@router.get("/study/consent")
def study_consent():
    return {"version": analytics.CONSENT_VERSION, "text": analytics.CONSENT_TEXT}


class StudyJoinIn(BaseModel):
    consent: bool = Field(description="True only when the participant ticked 'I agree to take part'.")


@router.post("/study/join", dependencies=[Depends(require_study_access)])
def study_join(body: StudyJoinIn, db: Session = Depends(get_db)):
    """Start a session under a random participant id; no name or contact details are stored."""
    if not body.consent:
        raise ApiError(400, "no_consent", "The participant has not agreed to take part")
    existing = set(db.scalars(select(Consent.participant_id)))
    pid = analytics.participant_id(existing)
    user = User(id=str(uuid.uuid4()), token=secrets.token_urlsafe(32), display_name=pid,
                variant=random.choice(AB_VARIANTS))
    db.add(user)
    db.flush()
    db.add(Consent(participant_id=pid, user_id=user.id, consent_version=analytics.CONSENT_VERSION))
    log_event(db, user, "study_joined")
    db.commit()
    return {"participant_id": pid, "user_id": user.id, "token": user.token, "variant": user.variant}


@router.delete("/admin/study/{participant_id}", dependencies=admin)
def study_withdraw(participant_id: str, db: Session = Depends(get_db)):
    """Withdrawal: delete everything stored for this participant."""
    c = db.get(Consent, participant_id)
    if not c:
        raise ApiError(404, "not_found", f"No participant {participant_id}")
    # Delete every row about this participant, not only the user: rows with
    # ondelete="SET NULL" (feedback text, tutor prompts, events) would otherwise stay.
    for model in (Feedback, LlmEvent, RecoEvent, Event):
        db.execute(delete(model).where(model.user_id == c.user_id))
    db.execute(delete(User).where(User.id == c.user_id))  # cascades to consent, onboarding, attempts, check-ins
    log_event(db, None, "study_withdrawn", participant_id=participant_id)
    db.commit()
    return {"deleted": participant_id}


def _benchmark(db: Session, user_id: str, stage: str) -> int | None:
    rows = db.scalars(select(BenchmarkAnswer.is_correct).where(
        BenchmarkAnswer.user_id == user_id, BenchmarkAnswer.stage == stage)).all()
    return sum(rows) if rows else None


@router.get("/admin/study", dependencies=admin)
def study_results(db: Session = Depends(get_db)):
    """Paired before/after results for participants: confidence and benchmark score."""
    pairs = []
    for c in db.scalars(select(Consent)):
        prof = db.get(Profile, c.user_id)
        pairs.append({"participant_id": c.participant_id,
                      "before": {"confidence": prof.confidence_before if prof else None,
                                 "score": _benchmark(db, c.user_id, "before")},
                      "after": {"confidence": prof.confidence_after if prof else None,
                                "score": _benchmark(db, c.user_id, "after")}})
    return analytics.study_report(pairs)


# ---------------------------------------------------------------- admin views

@router.get("/admin/overview", dependencies=admin)
def overview(db: Session = Depends(get_db)):
    """Tiles and alerts (view A)."""
    day = datetime.now(timezone.utc) - timedelta(days=1)
    rows = _rows(_attempts(db))
    items = analytics.item_stats([a for a in rows if a["level"] in ("easy", "medium")])
    llm = _llm_rows(db)
    tutor = analytics.tutor_overview(llm) if llm else None
    alerts = [{"kind": "report", **a} for a in analytics.report_alerts(_reports(db))]
    alerts += [{"kind": "item", "target_id": i["task_id"], "flags": i["flags"], "level": "amber"} for i in items if i["flags"]]
    if tutor and tutor["advice_alert"]["on"]:
        alerts.insert(0, {"kind": "advice", "level": "red", **tutor["advice_alert"]})
    return {
        "users": db.scalar(select(func.count()).select_from(User)),
        "attempts_last_24h": db.scalar(select(func.count()).select_from(Attempt).where(Attempt.submitted_at >= day)),
        "onboarded": db.scalar(select(func.count()).select_from(Onboarding)),
        "open_reports": db.scalar(select(func.count()).select_from(Feedback).where(Feedback.status.in_(("new", "triaged")))),
        "tutor_answers": tutor["n"] if tutor else 0, "tutor_fallback_rate": tutor["fallback_rate"] if tutor else None,
        "alerts": alerts,
    }


@router.get("/admin/items", dependencies=admin)
def admin_items(db: Session = Depends(get_db)):
    """Question and task quality from first attempts (view B)."""
    reports: dict[str, int] = {}
    for r in _reports(db):
        if r["kind"] == "wrong_fact" and r["status"] in ("new", "triaged"):
            reports[r["target_id"]] = reports.get(r["target_id"], 0) + 1
    rows = _rows(_attempts(db))
    return {"items": analytics.item_stats([a for a in rows if a["level"] in ("easy", "medium")], reports),
            "hard": analytics.hard_overview(rows)}


@router.get("/admin/calibration", dependencies=admin)
def admin_calibration(db: Session = Depends(get_db)):
    """How sure vs how right over time, overall and by age band (view C)."""
    groups = {o.user_id: o.survey.get("age_band", "unknown") for o in db.scalars(select(Onboarding))}
    self_rating = [{"self_rating": o.survey.get("self_rating"), "knowledge_score": o.result.get("knowledge_score")}
                   for o in db.scalars(select(Onboarding))]
    return {"series": analytics.calibration_series(_rows(_attempts(db)), groups), "onboarding_self_rating": self_rating}


@router.get("/admin/advice-watch", dependencies=admin)
def advice_watch(db: Session = Depends(get_db)):
    """Tutor overview (view D); empty until the tutor writes llm_events."""
    llm = _llm_rows(db)
    return analytics.tutor_overview(llm) if llm else {"n": 0}


# GET /admin/reco-events is Mo's route (app/admin.py).


@router.get("/admin/client-insights", dependencies=admin)
def admin_client_insights(min_group: int = 5, db: Session = Depends(get_db)):
    """Aggregate overview of our users for stakeholders: profile, knowledge, learning needs, paths,
    and what they said after the path. Groups smaller than min_group are hidden; nothing per person."""
    onb = [{"survey": o.survey, "result": o.result} for o in db.scalars(select(Onboarding))]
    chk = [{"path_id": c.path_id, "answers": c.answers} for c in db.scalars(select(PathCheckin))]
    return analytics.client_insights(onb, chk, max(5, min_group))


@router.get("/admin/node-opened", dependencies=admin)
def node_opened_summary(db: Session = Depends(get_db)):
    """Clicks by source; the self-chosen share is the next-step model's alternative signal."""
    rows = [e.payload for e in db.scalars(select(Event).where(Event.name == "node_opened"))]
    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r.get("source")] = by_source.get(r.get("source"), 0) + 1
    return {"total": len(rows), "by_source": by_source,
            "self_chosen_share": round(by_source.get("self_chosen", 0) / len(rows), 4) if rows else None}
