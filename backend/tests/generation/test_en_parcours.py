"""Parcours anglais : livrables choisis en anglais (dossier anglais ou mixte), exports DOCX/PPTX anglais."""

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pptx import Presentation
from sqlalchemy import select

from app.config import get_settings
from app.export.common import export_deliverable
from app.generation.template_loader import load_template
from app.llm import FakeProvider
from app.llm.demo import demo_handler
from app.main import create_app
from app.storage import schema as s
from tests.services.test_generation_fakes import honest

P = "/api/v1"
DOCS = [
    ("a.txt", (
        "Institutional context and challenges\n\nThe IT department manages forty business "
        "applications scattered across six services of the ministry.\n")),
    ("b.txt", (
        "Diagnostic findings\n\nThe digital steering committee meets every quarter "
        "to decide the priorities of the diagnostic.\n")),
    ("c.txt", (
        "Governance challenges\n\nCustomer data is stored in three databases without a "
        "common repository, which harms institutional challenges.\n")),
]


@pytest.fixture(params=["fake", "demo"])
def api(request, repo, monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    get_settings.cache_clear()
    provider = FakeProvider(handler=honest if request.param == "fake" else demo_handler)
    with TestClient(create_app(provider, repo)) as c:
        yield c
    get_settings.cache_clear()


def _setup(api, language):
    did = api.post(f"{P}/dossiers", json={"name": "D", "client_name": "C", "language": language}).json()["id"]
    for name, body in DOCS:
        r = api.post(f"{P}/dossiers/{did}/documents", files={"file": (name, body.encode())})
        assert r.status_code == 201, r.text
    ext = api.post(f"{P}/dossiers/{did}/findings:extract").json()
    assert ext["findings"], ext
    for f in ext["findings"]:
        assert api.patch(f"{P}/findings/{f['id']}", json={"validated": True}).status_code == 200
    return did


def _user(repo) -> str:
    with repo.engine.connect() as c:
        return c.execute(select(s.users.c.id)).first()[0]


@pytest.mark.parametrize("dossier_lang", ["en", "fr"])  # « fr » : dossier mixte, livrables choisis en anglais
def test_parcours_anglais_et_exports(api, repo, tmp_path, dossier_lang):
    did = _setup(api, dossier_lang)
    road = api.post(f"{P}/dossiers/{did}/roadmap:generate", json={"language": "en"})
    assert road.status_code == 200, road.text
    rid = road.json()["deliverable_id"]
    _, rc = repo.get_version(rid)
    assert rc.language == "en" and rc.template_id == "roadmap-en-standard"
    ini = road.json()["roadmap"]["items"][0]["initiative"]["id"]

    tor = api.post(f"{P}/dossiers/{did}/deliverables",
                   json={"type": "tor", "initiative_id": ini, "language": "en"})
    assert tor.status_code == 201, tor.text
    tid = tor.json()["deliverable_id"]
    for spec in load_template("tor", "en").sections:
        r = api.post(f"{P}/deliverables/{tid}/sections/{spec.key}:generate")
        assert r.status_code == 200, (spec.key, r.text)
        assert r.json()["status"] != "invalid"
        assert all(i["severity"] != "blocking" for i in r.json()["report"]["issues"]), r.json()["report"]
    _, content = repo.get_version(tid)
    assert content.language == "en" and content.template_id == "tor-en-standard"
    assert [d.section_key for d in content.sections] == [x.key for x in load_template("tor", "en").sections]

    uid = _user(repo)
    for d in (tid, rid):
        repo.set_state(d, "approved", uid, None)
    out = tmp_path / "out"
    path, _ = export_deliverable(repo, tid, "docx", uid, out)
    doc = Document(str(path))
    heads = [p.text for p in doc.paragraphs if p.style.name.startswith(("Heading", "Title"))]
    assert "Terms of Reference" in heads and "Background and rationale" in heads and "Sources" in heads
    assert any("Approved by" in p.text for sec in doc.sections for p in sec.footer.paragraphs)

    rpath, _ = export_deliverable(repo, rid, "pptx", uid, out)
    titles = [sl.shapes.title.text for sl in Presentation(str(rpath)).slides if sl.shapes.title is not None]
    assert "Executive summary" in titles and any(x.startswith("Wave ") for x in titles)
    assert any(t.startswith("Execution order") for t in titles)  # sans durées : pas de Gantt
    assert any(t.startswith("Priority matrix") for t in titles)
    rdoc, _ = export_deliverable(repo, rid, "docx", uid, out)
    heads = [p.text for p in Document(str(rdoc)).paragraphs]
    assert "Prioritised initiatives" in heads and "Findings → initiatives matrix" in heads


def test_langue_par_defaut_celle_du_dossier(api, repo):
    did = _setup(api, "fr")
    ini = api.post(f"{P}/dossiers/{did}/roadmap:generate", json={}).json()
    _, rc = repo.get_version(ini["deliverable_id"])
    assert rc.language == "fr"
    assert api.post(f"{P}/dossiers/{did}/deliverables", json={"type": "cdc", "language": "de"}).status_code == 422
