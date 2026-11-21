import re
"""Shared dependencies and the API error format."""
import hmac

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ADMIN_KEY, STUDY_KEY
from app.db import get_db
from app.models import Event, User


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    """Expects 'Authorization: Bearer <token>' from POST /auth/session."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "unauthorized", "Missing 'Authorization: Bearer <token>' header")
    user = db.scalar(select(User).where(User.token == authorization.split(" ", 1)[1].strip()))
    if not user:
        raise ApiError(401, "unauthorized", "Unknown or expired token")
    return user


class Guest:
    """A visitor without an account. Nothing about a guest is stored: the app keeps their history
    and sends it with each request (X-Guest-History), the server computes and forgets."""
    is_guest = True
    is_admin = False
    email = None
    token = None
    variant = "A"
    display_name = "You"

    def __init__(self, guest_id: str, history: list):
        self.id = guest_id
        self.history = history


def is_guest(viewer) -> bool:
    return getattr(viewer, "is_guest", False)


def _guest_history(raw: str | None) -> list:
    """[[task_id, node_id, level, context, score], ...] as sent by the app; bad input is ignored."""
    import json
    try:
        rows = json.loads(raw) if raw else []
    except ValueError:
        return []
    out = []
    for r in rows[:500] if isinstance(rows, list) else []:
        if (isinstance(r, list) and len(r) == 5 and all(isinstance(x, str) for x in r[:4])
                and (r[4] is None or isinstance(r[4], (int, float)))):
            out.append(r)
    return out


def viewer(authorization: str | None = Header(default=None), x_guest_id: str | None = Header(default=None),
           x_guest_history: str | None = Header(default=None), db: Session = Depends(get_db)):
    """The signed-in account (Bearer token), or a stateless Guest when there is no token."""
    if authorization and authorization.lower().startswith("bearer "):
        return current_user(authorization, db)
    gid = x_guest_id if x_guest_id and re.fullmatch(r"[A-Za-z0-9-]{8,64}", x_guest_id) else "guest"
    return Guest("guest-" + gid, _guest_history(x_guest_history))


def require_admin(x_admin_key: str | None = Header(default=None), key: str | None = None,
                  authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> None:
    """Admin endpoints: the ADMIN_KEY (header 'X-Admin-Key' or '?key='), or the token of a signed-in admin account."""
    if authorization and authorization.lower().startswith("bearer "):
        u = db.scalar(select(User).where(User.token == authorization.split(" ", 1)[1].strip()))
        if u is not None and u.is_admin:
            return
    _require_admin_key(x_admin_key, key)


def _require_admin_key(x_admin_key: str | None, key: str | None) -> None:
    """Admin endpoints need the ADMIN_KEY, as header 'X-Admin-Key' or query '?key=' (handy in a browser)."""
    given = x_admin_key or key or ""
    if not ADMIN_KEY or not hmac.compare_digest(given, ADMIN_KEY):
        raise ApiError(403, "forbidden", "Admin key required")


def require_study_access(x_study_key: str | None = Header(default=None), x_admin_key: str | None = Header(default=None)) -> None:
    """Starting a study session: the facilitator's STUDY_KEY (header 'X-Study-Key') or the ADMIN_KEY.
    Without it anyone could create unlimited participants and skew the study results."""
    if STUDY_KEY and x_study_key and hmac.compare_digest(x_study_key, STUDY_KEY):
        return
    if ADMIN_KEY and x_admin_key and hmac.compare_digest(x_admin_key, ADMIN_KEY):
        return
    raise ApiError(403, "forbidden", "Study key required")


def log_event(db: Session, user: User | None, name: str, **payload) -> None:
    db.add(Event(user_id=user.id if user else None, variant=user.variant if user else None, name=name, payload=payload))
