"""Scales, the app's points, kept on the server so leagues rank real learners.

Every award is one row in scale_events. The (user, source, ref) key makes each
award happen once: a task's correct answer, a finished mission, one daily
scenario per day, the quick check once. Amounts match the app (frontend
Rewards in lib/data/app_state.dart).
"""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ScaleEvent, User

AMOUNTS = {"correct": 10, "mission": 20, "daily_right": 15, "daily_tried": 5, "quick_check": 25}
LEVELS = [("Beginner", 0), ("Intermediate", 300), ("Expert", 1000)]


def award(db: Session, user_id: str, source: str, ref: str, when: datetime | None = None) -> int:
    """Add the award once; returns the Scales added (0 if this award was already given)."""
    key = "daily" if source.startswith("daily_") else source
    exists = db.scalar(select(ScaleEvent.id).where(ScaleEvent.user_id == user_id, ScaleEvent.source == key,
                                                   ScaleEvent.ref == ref))
    if exists:
        return 0
    amount = AMOUNTS[source]
    db.add(ScaleEvent(user_id=user_id, source=key, ref=ref, amount=amount, created_at=when or datetime.now(timezone.utc)))
    db.flush()
    return amount


def total(db: Session, user_id: str) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(ScaleEvent.amount), 0)).where(ScaleEvent.user_id == user_id)))


def level_of(scales: int) -> str:
    return [name for name, floor in LEVELS if scales >= floor][-1]


def leagues(db: Session, me: User, per_level: int = 50) -> dict:
    """Registered learners per level, ranked by Scales. Guests (no account), admin accounts and learners
    with no Scales are left out; a guest still sees their own row, so they know where they would stand."""
    rows = db.execute(select(User.id, User.display_name, func.sum(ScaleEvent.amount).label("n"))
                      .join(ScaleEvent, ScaleEvent.user_id == User.id)
                      .where(User.is_admin.is_(False), User.email.is_not(None))
                      .group_by(User.id, User.display_name)).all()
    totals = {uid: (name, int(n)) for uid, name, n in rows}
    if me.id not in totals and not me.is_admin:
        totals[me.id] = (me.display_name, total(db, me.id))
    out = []
    for i, (name, floor) in enumerate(LEVELS):
        ceiling = LEVELS[i + 1][1] if i + 1 < len(LEVELS) else None
        members = sorted(((n, nm, uid) for uid, (nm, n) in totals.items() if n >= floor and (ceiling is None or n < ceiling)),
                         key=lambda t: (-t[0], t[1]))
        out.append({"name": name, "min": floor, "max": ceiling, "total": len(members),
                    "entries": [{"rank": r + 1, "display_name": nm, "scales": n, "is_me": uid == me.id}
                                for r, (n, nm, uid) in enumerate(members[:per_level])]})
    mine = total(db, me.id)
    return {"me": {"scales": mine, "level": level_of(mine)}, "levels": out}
