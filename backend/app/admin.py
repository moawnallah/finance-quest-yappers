"""Admin monitoring (docs/tutor_agent.md, section 6): read-only views of the
backend event log, the tutor's model calls and the recommender events.
Every endpoint needs the admin key in the X-Admin-Key header. Users appear
only as pseudonymous ids (a hash of the user id), never by name."""
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Event, LlmEvent, RecoEvent, User

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def pseudo(user_id: str | None) -> str | None:
    return hashlib.sha256(user_id.encode()).hexdigest()[:10] if user_id else None


def log_llm_event(db: Session, user: User | None, **fields) -> LlmEvent:
    """For the tutor wiring (POST /tutor): store one model call. Pass masked text only."""
    row = LlmEvent(user_id=user.id if user else None, **fields)
    db.add(row)
    return row


def log_reco_event(db: Session, user: User | None, event_type: str, **fields) -> RecoEvent:
    """For the router wiring (POST /onboarding) and the recommender."""
    row = RecoEvent(user_id=user.id if user else None, event_type=event_type, **fields)
    db.add(row)
    return row


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """Counts for the overview cards: users, events, tutor calls in the last 24 h, flags, fallbacks."""
    day = datetime.now(timezone.utc) - timedelta(days=1)
    llm_day = select(func.count()).select_from(LlmEvent).where(LlmEvent.ts >= day)
    return {
        "users": db.scalar(select(func.count()).select_from(User)),
        "events": db.scalar(select(func.count()).select_from(Event)),
        "events_24h": db.scalar(select(func.count()).select_from(Event).where(Event.created_at >= day)),
        "llm_calls": db.scalar(select(func.count()).select_from(LlmEvent)),
        "llm_calls_24h": db.scalar(llm_day),
        "llm_flagged": db.scalar(select(func.count()).select_from(LlmEvent).where(LlmEvent.flagged_for_review.is_(True))),
        "llm_fallbacks": db.scalar(select(func.count()).select_from(LlmEvent).where(LlmEvent.fallback_used.is_(True))),
        "llm_avg_latency_ms": db.scalar(select(func.avg(LlmEvent.latency_ms))),
        "reco_events": db.scalar(select(func.count()).select_from(RecoEvent)),
    }


@router.get("/events")
def events(name: str | None = None, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    """The backend event log, newest first; filter by event name."""
    q = select(Event).order_by(Event.id.desc())
    if name:
        q = q.where(Event.name == name)
    rows = db.scalars(q.offset(offset).limit(limit)).all()
    names = db.execute(select(Event.name, func.count()).group_by(Event.name).order_by(func.count().desc())).all()
    return {
        "items": [{"id": e.id, "ts": e.created_at.isoformat() if e.created_at else None, "user": pseudo(e.user_id),
                   "variant": e.variant, "name": e.name, "payload": e.payload} for e in rows],
        "names": [{"name": n, "count": c} for n, c in names],
    }


@router.get("/llm-events")
def llm_events(flagged: bool | None = None, intent: str | None = None, limit: int = Query(50, ge=1, le=500),
               offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    """Tutor and router model calls, newest first, with the masked prompt and answer."""
    q = select(LlmEvent).order_by(LlmEvent.id.desc())
    if flagged is not None:
        q = q.where(LlmEvent.flagged_for_review.is_(flagged))
    if intent:
        q = q.where(LlmEvent.intent == intent)
    rows = db.scalars(q.offset(offset).limit(limit)).all()
    return {"items": [{
        "id": r.id, "ts": r.ts.isoformat() if r.ts else None, "user": pseudo(r.user_id), "screen": r.screen_id,
        "task": r.task_id, "node": r.node, "mode": r.mode, "intent": r.intent, "model_role": r.model_role,
        "model": r.model, "prompt_version": r.prompt_version, "latency_ms": r.latency_ms, "tokens_in": r.tokens_in,
        "tokens_out": r.tokens_out, "checks_failed": r.checks_failed or [], "fallback_used": r.fallback_used,
        "hint_level": r.hint_level, "user_rating": r.user_rating, "flagged": r.flagged_for_review,
        "prompt": r.prompt_masked, "answer": r.answer_masked} for r in rows]}


@router.get("/reco-events")
def reco_events(event_type: str | None = None, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                db: Session = Depends(get_db)):
    """Onboarding-router and recommender events, newest first."""
    q = select(RecoEvent).order_by(RecoEvent.id.desc())
    if event_type:
        q = q.where(RecoEvent.event_type == event_type)
    rows = db.scalars(q.offset(offset).limit(limit)).all()
    return {"items": [{
        "id": r.id, "ts": r.ts.isoformat() if r.ts else None, "user": pseudo(r.user_id), "type": r.event_type,
        "router_version": r.router_version, "node": r.node, "predicted_m": r.predicted_m, "observed": r.observed,
        "priority": r.priority, "reason": r.reason_term, "path": r.path, "payload": r.payload} for r in rows]}



@router.get("/tutor-metrics")
def tutor_metrics(db: Session = Depends(get_db)):
    """Per mode (docs/scaling.md "Admin panel"): requests, p50/p95 latency of model answers, fallback rate,
    cache hit rate, cold loads (load over 1 s) and prompt-eval p50, plus the cache size."""
    from statistics import median
    from app.models import TutorCache
    rows = db.scalars(select(LlmEvent)).all()
    def pct(xs, q):
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else None
    modes = {}
    for r in rows:
        modes.setdefault(r.mode or "unknown", []).append(r)
    out = []
    for m, rs in sorted(modes.items()):
        model = [r for r in rs if r.model != "cache" and not r.fallback_used and r.latency_ms is not None]
        lat = [r.latency_ms for r in model]
        pe = [r.prompt_eval_ms for r in model if r.prompt_eval_ms is not None]
        out.append({"mode": m, "requests": len(rs), "p50_ms": pct(lat, 0.5), "p95_ms": pct(lat, 0.95),
                    "fallback_rate": round(sum(r.fallback_used for r in rs) / len(rs), 3),
                    "cache_hit_rate": round(sum(r.model == "cache" for r in rs) / len(rs), 3),
                    "cold_loads": sum(1 for r in model if (r.load_ms or 0) > 1000),
                    "prompt_eval_p50_ms": int(median(pe)) if pe else None})
    return {"modes": out, "cache_entries": db.query(TutorCache).count()}


@router.delete("/tutor-cache")
def clear_tutor_cache(db: Session = Depends(get_db)):
    """After a content or prompt fix: forget every cached tutor answer."""
    from app.models import TutorCache
    n = db.query(TutorCache).delete()
    db.commit()
    return {"deleted": n}
