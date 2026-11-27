"""Lot 2 : une tâche longue se suit (étapes, avancement) et s'arrête."""

import time

import pytest

from app.config import get_settings
from app.services import jobs

V1 = "/api/v1"
TEXTE = "La Commission ne rend pas compte de son recours aux consultants externes. " * 40


@pytest.fixture
def c(client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    return client


def _wait(c, job_id, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        j = c.get(f"{V1}/jobs/{job_id}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.1)
    raise AssertionError("tâche jamais terminée")


def test_extraction_suivie_jusqu_au_bout(c):
    did = c.post(f"{V1}/dossiers", json={"name": "D", "client_name": "C"}).json()["id"]
    r = c.post(f"{V1}/dossiers/{did}/documents", files={"file": ("r.txt", TEXTE.encode())},
               data={"role": "diagnostic"})
    assert r.status_code == 201
    j = c.post(f"{V1}/dossiers/{did}/jobs", json={"kind": "findings"})
    assert j.status_code == 202
    done = _wait(c, j.json()["id"])
    assert done["status"] == "done", done
    assert done["total"] and done["done"] == done["total"]
    texts = [s["text"] for s in done["steps"]]
    assert texts[0] == "Démarrage" and texts[-1].startswith("Terminé")
    assert any("passage" in t for t in texts)
    assert c.get(f"{V1}/dossiers/{did}/jobs").json()[0]["id"] == done["id"]


def test_arret_demande_avant_un_appel():
    def fn():
        jobs.current().total(3, "lots")
        for _ in range(100):
            jobs.current().check()
            time.sleep(0.02)
        return {}

    job = jobs.start("findings", "dos_x", "test", fn)
    time.sleep(0.05)
    jobs.cancel(job.id)
    for _ in range(100):
        if job.status != "running":
            break
        time.sleep(0.02)
    assert job.status == "cancelled"
    assert "Arrêté" in job.view()["steps"][-1]["text"]


def test_tache_inconnue_404(c):
    assert c.get(f"{V1}/jobs/job_inexistant").status_code == 404
