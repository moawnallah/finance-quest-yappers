"""Settings read from environment variables, with local defaults."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent

_default_db = f"sqlite:///{BACKEND_DIR / 'finance_quest.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", _default_db)
# Hosted Postgres (e.g. Neon) gives postgres:// or postgresql:// URLs; use the psycopg 3 driver.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]
CONTENT_DIR = Path(os.getenv("CONTENT_DIR", BACKEND_DIR / "content"))

XP_PER_CORRECT = 10
XP_PER_PRACTICE = 5
AB_VARIANTS = ("A", "B")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")  # for /admin/* (or an admin account's token); empty = key access disabled
# Study mode: facilitators send this in X-Study-Key to start a participant session (or use the admin key).
STUDY_KEY = os.getenv("STUDY_KEY", "")

# Task engines (backend/data): compiled easy.json and medium_tasks.json
ENGINE_OUTPUT_DIR = Path(os.getenv("ENGINE_OUTPUT_DIR", BACKEND_DIR / "data" / "output"))
# Serve nodes and tasks that no reviewer has signed off yet (live: false). On for the demo; set to 0 in production.
SERVE_DRAFTS = os.getenv("SERVE_DRAFTS", "1") != "0"
