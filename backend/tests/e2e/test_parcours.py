"""Parcours complet sur le corpus or B4 : import → constats → validation → feuille de route → ToR."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import get_settings
from app.generation.template_loader import load_template
from app.llm import FakeProvider
from app.main import create_app
from app.storage import schema as s
from eval.corpus.generate import generate
from tests.services.test_generation_fakes import honest


@pytest.fixture
def api(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    get_settings.cache_clear()
    with TestClient(create_app(FakeProvider(handler=honest), repo)) as c:
        yield c
    get_settings.cache_clear()


def test_parcours_complet_institution_1(api, repo, tmp_path):
    t0 = time.perf_counter()
    gold = generate(7, tmp_path / "corpus")
    inst = gold.documents[0].institution
    did = api.post("/api/v1/dossiers", json={"name": inst, "client_name": inst}).json()["id"]
    for doc in (d for d in gold.documents if d.institution == inst):
        rel = next(iter(doc.paths.values()))  # un format par document suffit
        path = Path(tmp_path / "corpus" / rel)
        r = api.post(f"/api/v1/dossiers/{did}/documents", files={"file": (path.name, path.read_bytes())})
        assert r.status_code == 201, r.text

    ext = api.post(f"/api/v1/dossiers/{did}/findings:extract").json()
    assert ext["findings"], ext
    assert all(f["report"]["issues"] == [] for f in ext["findings"])
    for f in ext["findings"]:
        assert api.patch(f"/api/v1/findings/{f['id']}", json={"validated": True}).status_code == 200

    road = api.post(f"/api/v1/dossiers/{did}/roadmap:generate", json={})
    assert road.status_code == 200, road.text
    rid = road.json()["deliverable_id"]
    items = road.json()["roadmap"]["items"]
    assert items and items[0]["rank"] == 1
    ini = items[0]["initiative"]["id"]
    upd = api.patch(f"/api/v1/deliverables/{rid}/roadmap",
                    json={"initiatives": [{"id": ini, "duration_weeks": 8}]})
    assert upd.status_code == 200

    tor = api.post(f"/api/v1/dossiers/{did}/deliverables",
                   json={"type": "tor", "initiative_id": ini}).json()["deliverable_id"]
    for spec in load_template("tor", "fr").sections:
        r = api.post(f"/api/v1/deliverables/{tor}/sections/{spec.key}:generate")
        assert r.status_code == 200, (spec.key, r.text)
        assert r.json()["tpv"] == 1.0, (spec.key, r.json()["report"]["issues"])

    _, content = repo.get_version(tor)
    assert [d.section_key for d in content.sections] == [x.key for x in load_template("tor").sections]
    assert all(d.status == "ok" and d.sentences for d in content.sections)
    with repo.engine.connect() as c:
        n = lambda kind: c.execute(select(func.count()).select_from(s.generation_runs).where(
            s.generation_runs.c.kind == kind)).scalar()
        assert n("findings") >= 1 and n("initiatives") == 1 and n("section") == 6
        assert c.execute(select(func.count()).select_from(s.verification_results)).scalar() > 0
    assert time.perf_counter() - t0 < 30
