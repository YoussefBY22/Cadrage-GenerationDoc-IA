from fastapi.testclient import TestClient

from app.llm import FakeProvider
from app.main import create_app


def client():
    return TestClient(create_app(FakeProvider()))


def test_health():
    with client() as c:
        r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_ready_without_database_configured():
    with client() as c:
        r = c.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "unconfigured", "llm_provider": "fake-v1"}


def test_ready_503_when_database_unreachable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:secret@127.0.0.1:1/db")
    from app import config
    config.get_settings.cache_clear()
    try:
        with client() as c:
            r = c.get("/ready")
        assert r.status_code == 503
        assert "secret" not in r.text   # le mot de passe ne fuit jamais
    finally:
        config.get_settings.cache_clear()
