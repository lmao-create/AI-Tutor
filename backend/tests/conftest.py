"""Shared pytest fixtures: isolated temp database, settings, API client."""
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(scope="session")
def session_tmp():
    d = Path(tempfile.mkdtemp(prefix="codetutor_test_"))
    yield d


@pytest.fixture(autouse=True)
def configure_settings(session_tmp, monkeypatch):
    """Point settings at an isolated temp dir; disable env provider."""
    from app.config import settings
    monkeypatch.setattr(settings, "data_dir", session_tmp)
    monkeypatch.setattr(settings, "db_path", session_tmp / "codetutor.db")
    monkeypatch.setattr(settings, "secrets_path", session_tmp / "secrets.json")
    monkeypatch.setattr(settings, "exec_tmp_dir", session_tmp / "exec_tmp")
    monkeypatch.setattr(
        settings, "env_provider",
        {"name": "", "base_url": "", "model": "", "key": ""},
    )
    yield


@pytest.fixture()
def fresh_db(configure_settings, session_tmp):
    """A brand-new, migrated database per test. Also resets the rate limiter."""
    from app import db, ratelimit, secrets
    ratelimit._hits.clear()
    secrets.clear_stored_key()
    db_path = session_tmp / f"test_{uuid.uuid4().hex[:10]}.db"
    conn = db.connect(db_path)
    db.set_conn_for_tests(conn)
    yield db
    db.close()
    ratelimit._hits.clear()
    secrets.clear_stored_key()


@pytest.fixture()
def client(fresh_db):
    """TestClient with the app lifespan (migrations + seeding) applied."""
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def seeded(fresh_db):
    """Seed content explicitly for direct (non-HTTP) service tests."""
    from app.seed import seed_all
    from app.services.progress import ensure_user
    stats = seed_all()
    user = ensure_user()
    return {"stats": stats, "user": user}
