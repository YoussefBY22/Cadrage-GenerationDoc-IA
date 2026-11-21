"""Routes de génération et de constats (API), avec FakeProvider « honnête »."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.llm import FakeProvider
from app.main import create_app
from tests.services.test_generation_fakes import honest

DOCS = [
    ("a.txt", ("Contexte institutionnel et enjeux\n\nLa direction informatique gère quarante "
              "applications métiers dispersées dans six services du ministère.\n")),
    ("b.txt", ("Constats du diagnostic\n\nLe comité de pilotage numérique se réunit chaque trimestre "
              "pour arbitrer les priorités du diagnostic.\n")),
    ("c.txt", ("Enjeux de gouvernance\n\nLes données clients sont stockées dans trois bases sans "
              "référentiel commun, ce qui nuit aux enjeux institutionnels.\n")),
]


@pytest.fixture
def api(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    get_settings.cache_clear()
    with TestClient(create_app(FakeProvider(handler=honest), repo)) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture
def dossier(api):
    did = api.post("/api/v1/dossiers", json={"name": "D", "client_name": "C"}).json()["id"]
    for name, body in DOCS:
        r = api.post(f"/api/v1/dossiers/{did}/documents", files={"file": (name, body.encode())})
        assert r.status_code == 201, r.text
    return did


def test_extraction_validation_et_correction(api, dossier):
    r = api.post(f"/api/v1/dossiers/{dossier}/findings:extract")
    assert r.status_code == 200 and r.json()["findings"] and not r.json()["rejected"]
    fid = r.json()["findings"][0]["id"]
    assert len(api.get(f"/api/v1/dossiers/{dossier}/findings").json()) == len(r.json()["findings"])
    assert api.get(f"/api/v1/dossiers/{dossier}/findings?validated_only=true").json() == []
    ok = api.patch(f"/api/v1/findings/{fid}", json={"validated": True})
    assert ok.status_code == 200 and ok.json()["validated"] is True
    # texte corrigé avec chiffre inventé : bloquant, validation refusée
    bad = api.patch(f"/api/v1/findings/{fid}", json={"text": "Le budget atteint 98765 euros.",
                                                     "validated": True})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "UNVERIFIED_FINDING"
    # texte corrigé seul : dévalidé
    edit = api.patch(f"/api/v1/findings/{fid}", json={"text": "La direction gère quarante applications."})
    assert edit.json()["validated"] is False
    assert api.patch("/api/v1/findings/fnd_inconnu", json={"validated": True}).status_code == 404


def test_feuille_de_route_exige_constats_valides(api, dossier):
    r = api.post(f"/api/v1/dossiers/{dossier}/roadmap:generate", json={})
    assert r.status_code == 409 and r.json()["error"]["code"] == "NO_VALIDATED_FINDINGS"


def test_objets_inconnus_ou_dossier_inconnu_404(api, dossier):
    assert api.post("/api/v1/dossiers/dos_x/findings:extract").status_code == 404
    assert api.post("/api/v1/dossiers/dos_x/roadmap:generate", json={}).status_code == 404
    assert api.post("/api/v1/dossiers/dos_x/deliverables", json={"type": "tor"}).status_code == 404
    assert api.post("/api/v1/deliverables/dlv_x/sections/contexte:generate").status_code == 404
    assert api.patch("/api/v1/deliverables/dlv_x/roadmap",
                     json={"initiatives": [{"id": "x"}]}).status_code == 404


def test_creation_livrable_et_section(api, dossier):
    bad = api.post(f"/api/v1/dossiers/{dossier}/deliverables", json={"type": "roadmap"})
    assert bad.status_code == 422
    no_ini = api.post(f"/api/v1/dossiers/{dossier}/deliverables",
                      json={"type": "tor", "initiative_id": "ini_x"})
    assert no_ini.status_code == 404
    dl = api.post(f"/api/v1/dossiers/{dossier}/deliverables", json={"type": "tor"}).json()
    r = api.post(f"/api/v1/deliverables/{dl['deliverable_id']}/sections/contexte:generate")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok" and body["tpv"] == 1.0 and body["version"] == 2
    assert api.post(f"/api/v1/deliverables/{dl['deliverable_id']}/sections/nope:generate"
                    ).status_code == 404
