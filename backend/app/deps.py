"""Shared dependencies and the API error format."""
import hmac

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ADMIN_KEY
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


def require_admin(x_admin_key: str | None = Header(default=None), key: str | None = None) -> None:
    """Admin endpoints need the ADMIN_KEY, as header 'X-Admin-Key' or query '?key=' (handy in a browser)."""
    given = x_admin_key or key or ""
    if not ADMIN_KEY or not hmac.compare_digest(given, ADMIN_KEY):
        raise ApiError(403, "forbidden", "Admin key required")


def log_event(db: Session, user: User | None, name: str, **payload) -> None:
    db.add(Event(user_id=user.id if user else None, variant=user.variant if user else None, name=name, payload=payload))
