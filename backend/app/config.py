"""Settings read from environment variables, with local defaults."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent

# On Vercel only /tmp is writable: the demo keeps SQLite there and rebuilds it on each cold start (see app.main).
ON_VERCEL = bool(os.getenv("VERCEL"))
_default_db = "sqlite:////tmp/finance_quest.db" if ON_VERCEL else f"sqlite:///{BACKEND_DIR / 'finance_quest.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", _default_db)
CONTENT_DIR = Path(os.getenv("CONTENT_DIR", BACKEND_DIR / "content"))

XP_PER_CORRECT = 10
XP_PER_PRACTICE = 5
AB_VARIANTS = ("A", "B")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")  # required for /admin/*; empty = admin endpoints disabled

# Task engines (backend/data): compiled easy.json and medium_tasks.json
ENGINE_OUTPUT_DIR = Path(os.getenv("ENGINE_OUTPUT_DIR", BACKEND_DIR / "data" / "output"))
# Serve nodes and tasks that no reviewer has signed off yet (live: false). On for the demo; set to 0 in production.
SERVE_DRAFTS = os.getenv("SERVE_DRAFTS", "1") != "0"
