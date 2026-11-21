"""Un module routes_* ajouté au paquet app.api est inclus sous /api/v1 sans toucher main.py."""

import sys

from fastapi import APIRouter
from fastapi.testclient import TestClient

import app.api as api_pkg
from app.llm.fake import FakeProvider
from app.main import create_app


def test_fake_routes_module_is_included(tmp_path, monkeypatch):
    (tmp_path / "routes_zz_fake.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/ping-fake')\n"
        "def ping():\n"
        "    return {'pong': True}\n",
        encoding="utf-8")
    (tmp_path / "other.py").write_text("router = None\n", encoding="utf-8")
    monkeypatch.setattr(api_pkg, "__path__", [*api_pkg.__path__, str(tmp_path)])
    try:
        routers = api_pkg.discover_routers()
        assert all(isinstance(r, APIRouter) for r in routers)
        client = TestClient(create_app(FakeProvider(), repo=object()))
        assert client.get("/api/v1/ping-fake").json() == {"pong": True}
        assert client.get("/health").status_code == 200
    finally:
        sys.modules.pop("app.api.routes_zz_fake", None)


def test_no_routes_is_fine():
    assert isinstance(api_pkg.discover_routers(), list)
