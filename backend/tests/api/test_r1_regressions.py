"""Non-régression du lot R1 (revue d'intégration) : CORS, format d'erreur unique, modèle « demo »."""

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.llm import FakeProvider, build_provider
from app.main import create_app

BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def token_client(repo, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "token")
    get_settings.cache_clear()
    with TestClient(create_app(FakeProvider(), repo)) as c:
        yield c
    get_settings.cache_clear()


def test_cors_preflight_from_front_dev_origin(token_client):
    r = token_client.options(
        "/api/v1/dossiers",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_refuses_other_origin(token_client):
    r = token_client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_disabled_when_empty():
    assert Settings(cors_origins="").cors_origin_list == []


def test_401_uses_error_envelope(token_client):
    r = token_client.get("/api/v1/dossiers")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"
    assert r.headers["www-authenticate"] == "Bearer"


def test_422_uses_error_envelope(token_client):
    r = token_client.post("/api/v1/auth/login", json={"email": "a@b.c"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR" and "password" in body["error"]["message"]


def test_unknown_route_uses_error_envelope(token_client):
    r = token_client.get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_demo_provider_is_grounded():
    p = build_provider(Settings(llm_provider="demo"))
    from app.generation.llm_schemas import LLMSection

    prompt = ("<<PASSAGE id=P1 nonce=ab12>>\nLe taux de pertes du réseau est de 32 % en 2023.\n"
              "<<FIN nonce=ab12>>")
    out = p.generate_structured(prompt, LLMSection)
    assert out.status == "ok" and out.sentences[0].sources == ["P1"]
    assert "32 %" in out.sentences[0].text
    empty = p.generate_structured("aucun passage", LLMSection)
    assert empty.status == "insufficient_evidence"


def test_create_user_script(tmp_path):
    env = {"STORAGE_URL": f"sqlite+pysqlite:///{(tmp_path / 'u.db').as_posix()}",
           "CADRAGE_PASSWORD": "un-mot-de-passe-long", "PATH": "", "SYSTEMROOT": "C:\\Windows"}
    run = lambda *a: subprocess.run([sys.executable, "scripts/create_user.py", *a], check=False, cwd=BACKEND,
                                    env=env, capture_output=True, text=True)
    first = run("a@exemple.fr", "Alice", "consultant")
    assert first.returncode == 0 and first.stdout.startswith("usr_")
    assert run("a@exemple.fr", "Alice", "consultant").returncode == 1  # doublon
    assert run("b@exemple.fr", "Bob", "dieu").returncode == 2  # rôle invalide


@pytest.mark.slow
def test_demo_parcours_runs_end_to_end(tmp_path):
    r = subprocess.run([sys.executable, "scripts/demo_parcours.py", "--out", str(tmp_path)],
                       cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=240)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    assert (tmp_path / "tor.docx").stat().st_size > 5000
    assert (tmp_path / "tor.pptx").stat().st_size > 5000
