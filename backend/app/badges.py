"""Badges: awarded automatically from data we already store. Each rule is a small query; awards are idempotent."""
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import progress
from app.models import Answer, BenchmarkAnswer, Node, NodeProgress, Question, Slice, UserBadge


def _first_step(db: Session, uid: str) -> bool:
    return bool(db.scalar(select(func.count()).select_from(NodeProgress).where(NodeProgress.user_id == uid)))


def _slice_master(db: Session, uid: str) -> bool:
    done = progress.completed_nodes(db, uid)
    for sl in db.scalars(select(Slice)):
        ids = [n.id for n in sl.nodes if not n.retired]
        if ids and all(i in done for i in ids):
            return True
    return False


def _held_in_crash(db: Session, uid: str) -> bool:
    rows = db.execute(select(Answer.choice, Question.options).join(Question, Question.id == Answer.question_id)
                      .where(Answer.user_id == uid, Question.kind == "behaviour"))
    return any(opts[c].lower().startswith("hold") for c, opts in rows if c < len(opts))


def _above_poland(db: Session, uid: str) -> bool:
    for stage in ("before", "after"):
        rows = db.scalars(select(BenchmarkAnswer.is_correct).where(
            BenchmarkAnswer.user_id == uid, BenchmarkAnswer.stage == stage)).all()
        if rows and sum(rows) >= 4:
            return True
    return False


def _streak(n: int) -> Callable[[Session, str], bool]:
    return lambda db, uid: progress.streak_days(db, uid) >= n


BADGES: dict[str, dict] = {
    "first_step": {"title": "First step", "description": "Completed your first node.", "icon": "flag", "rule": _first_step},
    "slice_master": {"title": "Slice master", "description": "Finished every node in one wheel slice.", "icon": "pie", "rule": _slice_master},
    "survived_2008": {"title": "Survived 2008", "description": "Chose to hold when the market crashed.", "icon": "shield", "rule": _held_in_crash},
    "above_poland": {"title": "Above Poland", "description": "4 or 5 of 5 on the EU quiz; only 20% of Poles manage that.", "icon": "medal", "rule": _above_poland},
    "streak_3": {"title": "3-day streak", "description": "Learned 3 days in a row.", "icon": "flame", "rule": _streak(3)},
    "streak_7": {"title": "7-day streak", "description": "Learned 7 days in a row.", "icon": "flame", "rule": _streak(7)},
}


def public(key: str) -> dict:
    b = BADGES[key]
    return {"key": key, "title": b["title"], "description": b["description"], "icon": b["icon"]}


def evaluate(db: Session, uid: str) -> list[dict]:
    """Award any badges the user now qualifies for. Returns only the newly awarded ones."""
    have = set(db.scalars(select(UserBadge.badge_key).where(UserBadge.user_id == uid)))
    new = []
    for key, b in BADGES.items():
        if key not in have and b["rule"](db, uid):
            db.add(UserBadge(user_id=uid, badge_key=key))
            new.append(public(key))
    return new
