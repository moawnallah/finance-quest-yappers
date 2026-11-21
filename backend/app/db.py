"""Database engine, session and declarative base."""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL

is_sqlite = DATABASE_URL.startswith("sqlite")
engine = (
    create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    if is_sqlite
    # Serverless instances sleep: check each pooled connection before use and keep the pool small.
    else create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=2, max_overflow=3, pool_recycle=300)
)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
