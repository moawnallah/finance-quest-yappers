"""Shared fixtures: one temporary SQLite database (migrations + seed) for the whole test session."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("db")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp / 'test.db'}"
    os.environ["ADMIN_KEY"] = "test-admin-key"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True, env=os.environ.copy())
    subprocess.run([sys.executable, "-m", "app.seed"], cwd=BACKEND, check=True, env=os.environ.copy())
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="session")
def auth(client):
    r = client.post("/auth/session", json={"display_name": "Zofia"})
    assert r.status_code == 200 and r.json()["variant"] in ("A", "B")
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    r = client.post("/me/profile", headers=h, json={"age_group": "18-29", "goal": "habit", "experience": "none", "confidence_before": 2})
    assert r.status_code == 200
    return h
