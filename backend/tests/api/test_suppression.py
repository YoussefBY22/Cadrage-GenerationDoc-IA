"""Lot 1 : lire un document, supprimer un document / un dossier / un livrable, fusion ≠ manquant."""

import pytest

from app.config import get_settings
from app.services import projet

V1 = "/api/v1"
TEXTE = "Rapport d'audit.\n\nLa Commission ne rend pas compte de son recours aux consultants externes. " * 20


@pytest.fixture
def c(client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    return client


def _dossier(c):
    return c.post(f"{V1}/dossiers", json={"name": "D", "client_name": "C"}).json()["id"]


def _upload(c, did, name="rapport.txt"):
    r = c.post(f"{V1}/dossiers/{did}/documents", files={"file": (name, TEXTE.encode())},
               data={"role": "diagnostic"})
    assert r.status_code == 201, r.text
    return r.json()["document_id"]


def test_fichier_affiche_inline(c):
    did = _dossier(c)
    doc = _upload(c, did)
    r = c.get(f"{V1}/documents/{doc}/file")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("inline")
    assert b"Commission" in r.content


def test_supprimer_document_emporte_passages_et_constats(c, repo):
    did = _dossier(c)
    doc = _upload(c, did)
    chunks = [ch.id for ch in repo.iter_chunks(did, [doc])]
    from app.domain.generation import Finding
    repo.save_findings(did, [Finding(id="fnd_a", dossier_id=did, text="x", theme="t", severity="low",
                                     source_ids=chunks[:1])])
    p = c.get(f"{V1}/documents/{doc}/delete-preview").json()
    assert p["findings"] == 1 and p["passages"] == len(chunks)
    assert c.delete(f"{V1}/documents/{doc}").status_code == 200
    assert c.get(f"{V1}/documents/{doc}").status_code == 404
    assert repo.list_findings(did) == []


def test_supprimer_dossier_complet(c):
    did = _dossier(c)
    _upload(c, did)
    p = c.get(f"{V1}/dossiers/{did}/delete-preview").json()
    assert p["documents"] == 1
    assert c.delete(f"{V1}/dossiers/{did}").status_code == 200
    assert c.get(f"{V1}/dossiers/{did}").status_code == 404
    assert all(d["id"] != did for d in c.get(f"{V1}/dossiers").json())


def test_liste_des_livrables_vide(c):
    did = _dossier(c)
    assert c.get(f"{V1}/dossiers/{did}/deliverables").json() == []


def test_fusion_n_est_pas_un_manque():
    actives = [{"number": 1}, {"number": 3}, {"number": 4}]
    assert projet.controle([1, 2, 3, 4], actives, True, False)["missing"] == [2]
    ok = projet.controle([1, 2, 3, 4], actives, True, False, traites=[2])
    assert ok["missing"] == [] and ok["status"] == "ok"
