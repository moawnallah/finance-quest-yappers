"""The bank-side views of the admin panel (task group E): consent, learner cards, adviser signals,
recommender and AI quality, and exports. Individual data only for learners who share their profile
(and synthetic demo learners); everyone else appears only in aggregates."""
import csv
import io
import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin import pseudo
from app.db import get_db
from app.deps import ApiError, current_user, require_admin
from app.engines import catalog, node_status
from app.insights_api import _attempts, _rows, onboarding_router
from app.models import Attempt, Event, LlmEvent, Onboarding, PathCheckin, RecoEvent, User

import analytics  # noqa: E402  (backend/ml on sys.path via insights_api)

router = APIRouter(tags=["bank"])
admin = [Depends(require_admin)]


class ConsentIn(BaseModel):
    share: bool


@router.put("/me/consent")
def set_consent(body: ConsentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """"Share my learning profile with the bank": off by default; turning it off withdraws it."""
    user.share_profile = body.share
    db.commit()
    return {"share_profile": user.share_profile}


def _visible(db: Session, synthetic: bool = True) -> list[User]:
    q = select(User).where(User.share_profile.is_(True) | User.synthetic.is_(True)) if synthetic else \
        select(User).where(User.share_profile.is_(True), User.synthetic.is_(False))
    return list(db.scalars(q.where(User.is_admin.is_(False))))


def _done(db: Session, user_id: str) -> set[str]:
    cat, by = catalog(), {}
    for a in _attempts(db, user_id):
        by.setdefault(a.node_id, []).append(a)
    return {n for n, rows in by.items() if n in cat.nodes and node_status(cat, n, user_id, rows).get("done")}


def _last_confidence(db: Session, user_id: str) -> int | None:
    c = db.scalars(select(PathCheckin).where(PathCheckin.user_id == user_id).order_by(PathCheckin.id.desc())).first()
    vals = list(((c.answers or {}).get("confidence") or {}).values()) if c else []
    return round(sum(vals) / len(vals)) if vals else None


@router.get("/admin/learners", dependencies=admin)
def learners(db: Session = Depends(get_db)):
    """Learners who share their profile, plus synthetic demo learners (pseudonymous ids)."""
    out = []
    for u in _visible(db):
        onb = db.get(Onboarding, u.id)
        path = [p["node"] for p in (onb.result.get("path", []) if onb else [])]
        done = _done(db, u.id)
        out.append({"pseudo": pseudo(u.id), "synthetic": u.synthetic, "goal": (onb.survey or {}).get("goal") if onb else None,
                    "path": path, "done": sorted(done & set(path)), "progress": round(len(done & set(path)) / len(path), 2) if path else 0})
    return {"learners": sorted(out, key=lambda x: (-x["progress"], x["pseudo"])),
            "synthetic": any(x["synthetic"] for x in out)}


@router.get("/admin/learners/{pseudo_id}", dependencies=admin)
def learner_card(pseudo_id: str, db: Session = Depends(get_db)):
    """One learner's card. 404 unless they share their profile (or are synthetic)."""
    u = next((x for x in _visible(db) if pseudo(x.id) == pseudo_id), None)
    if u is None:
        raise ApiError(404, "not_found", "No learner with this id who shares their profile")
    cat = catalog()
    atts = _attempts(db, u.id)
    by: dict[str, list[Attempt]] = {}
    for a in atts:
        by.setdefault(a.node_id, []).append(a)
    states = {n: node_status(cat, n, u.id, by.get(n, [])) for n in cat.nodes}
    onb = db.get(Onboarding, u.id)
    summary = analytics.profile_summary(_rows(atts), onboarding_router.tree(), states, onb.result if onb else None)
    done = {n for n, st in states.items() if st.get("done")}
    nxt = onboarding_router.next_steps(onb.survey, onb.result, done) if onb else []
    reasons = [{"node": p["node"], "title": p.get("title"), "reason": p.get("reason")} for p in (onb.result.get("path", []) if onb else [])]
    events = db.scalars(select(Event).where(Event.user_id == u.id).order_by(Event.id.desc()).limit(40)).all()
    return {"pseudo": pseudo_id, "synthetic": u.synthetic, "summary": summary, "need_reasons": reasons,
            "next_steps": [{**x, "live": x["node"] in cat.nodes} for x in nxt],
            "timeline": [{"ts": e.created_at.isoformat() if e.created_at else None, "name": e.name} for e in events]}


@router.get("/admin/adviser-signals", dependencies=admin)
def adviser_signals(db: Session = Depends(get_db)):
    """Conversation signals at the level of types (never a product), for consenting and synthetic learners."""
    rows = [{"pseudo": pseudo(u.id), "synthetic": u.synthetic, "survey": (db.get(Onboarding, u.id).survey if db.get(Onboarding, u.id) else {}),
             "done": _done(db, u.id), "confidence": _last_confidence(db, u.id)} for u in _visible(db)]
    sig = analytics.adviser_signals(rows)
    return {"signals": sig, "synthetic": any(x["synthetic"] for x in sig)}


@router.get("/admin/ai-quality", dependencies=admin)
def ai_quality(db: Session = Depends(get_db)):
    """Recommender and AI quality: router path vs chosen vs finished, next steps shown, BASAL shadow
    agreement (when logged), tutor fallback rate and advice watch."""
    recos = db.scalars(select(RecoEvent)).all()
    count = lambda t: sum(1 for r in recos if r.event_type == t)
    chosen: dict[str, int] = {}
    for r in recos:
        if r.event_type == "path_chosen":
            k = (r.payload or {}).get("chosen") or "?"
            chosen[k] = chosen.get(k, 0) + 1
    shadow = [r.payload or {} for r in recos if r.event_type == "shadow_decision"]
    agree = [p.get("agreement") for p in shadow if isinstance(p.get("agreement"), (int, float))]
    llm = [{"ts": e.ts, "intent": e.intent, "checks_failed": e.checks_failed or [], "fallback_used": e.fallback_used,
            "flagged_for_review": e.flagged_for_review, "latency_ms": e.latency_ms, "model": e.model} for e in db.scalars(select(LlmEvent))]
    synthetic = db.scalar(select(User.id).where(User.synthetic.is_(True)).limit(1)) is not None
    return {"recommended": db.query(Onboarding).count(), "chosen": chosen, "chosen_total": sum(chosen.values()),
            "finished": count("path_finished"), "next_steps_shown": count("next_steps_shown"),
            "shadow": {"decisions": len(shadow), "errors": sum(1 for p in shadow if p.get("error")),
                       "agreement": round(sum(agree) / len(agree), 3) if agree else None},
            "tutor": analytics.tutor_overview(llm) if llm else {"n": 0}, "synthetic": synthetic}


EXPORTS = {
    "attempts": ["user", "task_id", "node_id", "level", "context", "score", "confidence", "points", "duration_ms", "submitted_at"],
    "reco_events": ["user", "ts", "event_type", "router_version", "node", "predicted_m", "need", "priority", "path"],
    "llm_events": ["user", "ts", "mode", "intent", "model", "latency_ms", "tokens_in", "tokens_out", "fallback_used",
                   "flagged_for_review", "checks_failed"],
    "surveys": ["user", "created_at", "age_band", "goal", "horizon", "self_rating", "experience", "knowledge_score", "band"],
}


@router.get("/admin/export", dependencies=admin)
def export(table: str, format: str = "csv", synthetic: int = 0, db: Session = Depends(get_db)):
    """CSV for the bank's data platform (contract: docs/admin_and_profile.md, "Export"). Pseudonymous ids,
    consenting learners only, no free text; synthetic rows only with synthetic=1."""
    if table not in EXPORTS or format != "csv":
        raise ApiError(400, "invalid_request", f"table must be one of {sorted(EXPORTS)} and format csv")
    users = {u.id: u for u in db.scalars(select(User).where(User.share_profile.is_(True) | User.synthetic.is_(True)))}
    ok = {uid for uid, u in users.items() if (u.share_profile and not u.synthetic) or (synthetic and u.synthetic)}
    rows = []
    if table == "attempts":
        for a in db.scalars(select(Attempt).where(Attempt.user_id.in_(ok))):
            rows.append([pseudo(a.user_id), a.task_id, a.node_id, a.level, a.context, a.score, a.confidence, a.points,
                         a.duration_ms, a.submitted_at.isoformat() if a.submitted_at else ""])
    elif table == "reco_events":
        for r in db.scalars(select(RecoEvent).where(RecoEvent.user_id.in_(ok))):
            rows.append([pseudo(r.user_id), r.ts.isoformat() if r.ts else "", r.event_type, r.router_version, r.node,
                         r.predicted_m, r.need, r.priority, json.dumps(r.path) if r.path is not None else ""])
    elif table == "llm_events":
        for e in db.scalars(select(LlmEvent).where(LlmEvent.user_id.in_(ok))):
            rows.append([pseudo(e.user_id), e.ts.isoformat() if e.ts else "", e.mode, e.intent, e.model, e.latency_ms,
                         e.tokens_in, e.tokens_out, e.fallback_used, e.flagged_for_review, json.dumps(e.checks_failed or [])])
    else:
        for o in db.scalars(select(Onboarding).where(Onboarding.user_id.in_(ok))):
            sv, rs = o.survey or {}, o.result or {}
            rows.append([pseudo(o.user_id), o.created_at.isoformat() if o.created_at else "", sv.get("age_band"), sv.get("goal"),
                         sv.get("horizon"), sv.get("self_rating"), sv.get("experience"), rs.get("knowledge_score"), rs.get("band")])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(EXPORTS[table])
    w.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="crococash-{table}.csv"'})
