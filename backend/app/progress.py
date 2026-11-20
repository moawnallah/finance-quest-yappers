"""Node unlock rules, XP and streaks. The backend is the only place that decides node states."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import XP_PER_CORRECT, XP_PER_PRACTICE
from app.models import Answer, Node, NodeProgress, NodeRequire, Question, Slice


def completed_nodes(db: Session, user_id: str) -> set[str]:
    return set(db.scalars(select(NodeProgress.node_id).where(NodeProgress.user_id == user_id)))


def requires_map(db: Session, node_ids: list[str]) -> dict[str, list[str]]:
    out = {n: [] for n in node_ids}
    for r in db.scalars(select(NodeRequire).where(NodeRequire.node_id.in_(node_ids))):
        out[r.node_id].append(r.requires_id)
    return out


def node_states(db: Session, user_id: str, sl: Slice) -> list[dict]:
    nodes = [n for n in sl.nodes if not n.retired]
    done = completed_nodes(db, user_id)
    reqs = requires_map(db, [n.id for n in nodes])
    titles = {n.id: n.title for n in nodes}
    out, current_set = [], False
    for n in nodes:
        missing = [r for r in reqs[n.id] if r not in done]
        if n.id in done:
            state, reason = "done", None
        elif missing:  # never blocked: the learner may skip ahead, we only suggest an order
            state, reason = "ahead", "We suggest " + " and ".join(titles.get(m, m) for m in missing) + " first"
        elif not current_set:
            state, reason, current_set = "current", None, True
        else:
            state, reason = "open", None
        out.append({"id": n.id, "title": n.title, "requires": reqs[n.id], "state": state, "hint": reason})
    return out


def slice_progress(db: Session, user_id: str, sl: Slice) -> float:
    nodes = [n.id for n in sl.nodes if not n.retired]
    if not nodes:
        return 0.0
    done = completed_nodes(db, user_id)
    return round(sum(1 for n in nodes if n in done) / len(nodes), 2)


def maybe_complete_node(db: Session, user_id: str, node: Node) -> tuple[bool, list[str]]:
    """A node is complete when every active question has an answer (scored ones answered correctly).
    Returns (completed_now, newly_unlocked_node_ids)."""
    if db.get(NodeProgress, (user_id, node.id)):
        return False, []
    for q in node.questions:
        if q.retired:
            continue
        cond = [Answer.user_id == user_id, Answer.question_id == q.id]
        if q.kind == "objective":
            cond.append(Answer.is_correct.is_(True))
        if not db.scalar(select(func.count()).select_from(Answer).where(*cond)):
            return False, []
    before = {n["id"] for n in node_states(db, user_id, node.slice) if n["state"] in ("current", "open")}
    db.add(NodeProgress(user_id=user_id, node_id=node.id))
    db.flush()
    after = {n["id"] for n in node_states(db, user_id, node.slice) if n["state"] in ("current", "open")}
    return True, sorted(after - before - {node.id})


def xp_for(question: Question, is_correct: bool | None, first_time: bool) -> int:
    if not first_time:
        return 0
    if question.kind == "objective":
        return XP_PER_CORRECT if is_correct else 0
    return XP_PER_PRACTICE


def total_xp(db: Session, user_id: str, since: datetime | None = None) -> int:
    """XP is earned once per question, at the first rewarding answer. With 'since', only XP earned after it."""
    xp = 0
    seen = set()
    rows = db.execute(
        select(Answer.question_id, Answer.is_correct, Question.kind, Answer.created_at)
        .join(Question, Question.id == Answer.question_id)
        .where(Answer.user_id == user_id).order_by(Answer.id)
    )
    for qid, ok, kind, created in rows:
        if qid in seen or (kind == "objective" and not ok):
            continue
        seen.add(qid)
        if since is None or _aware(created) >= since:
            xp += XP_PER_CORRECT if kind == "objective" else XP_PER_PRACTICE
    return xp


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def week_start(now: datetime | None = None) -> datetime:
    """Monday 00:00 UTC of the current week (leaderboards reset weekly)."""
    now = now or datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).date()
    return datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)


def streak_days(db: Session, user_id: str, today: date | None = None) -> int:
    days = {d.date() for d in db.scalars(select(Answer.created_at).where(Answer.user_id == user_id))}
    today = today or date.today()
    streak, d = 0, today
    if d not in days:
        d -= timedelta(days=1)  # streak survives until the end of today
    while d in days:
        streak += 1
        d -= timedelta(days=1)
    return streak
