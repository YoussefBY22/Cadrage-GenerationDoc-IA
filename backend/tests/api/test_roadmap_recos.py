"""Lot 4 : la feuille de route part des recommandations du rapport, chaque vague est justifiée."""

from datetime import date

import pytest

from app.config import get_settings
from app.domain.generation import Finding
from app.services.roadmap_recos import wave_for

V1 = "/api/v1"
RAPPORT = (
    "20 La Commission ne documentait pas ses besoins avant de recourir aux consultants externes.\n\n"
    "86 Nous avons relevé d'importantes lacunes dans le cadre (points 18 à 26).\n\n"
    "Recommandation n° 1 – Compléter le cadre régissant le recours aux consultants\n"
    "La Commission devrait développer son cadre. Ce cadre devrait:\n"
    "a) définir les formes de soutien;\nb) comporter des orientations sur les besoins;\n"
    "Quand? D'ici à décembre 2023.\n"
)


@pytest.fixture
def c(client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    return client


def test_feuille_de_route_depuis_les_recommandations(c, repo):
    did = c.post(f"{V1}/dossiers", json={"name": "D", "client_name": "C"}).json()["id"]
    doc = c.post(f"{V1}/dossiers/{did}/documents", files={"file": ("r.txt", RAPPORT.encode())},
                 data={"role": "diagnostic"}).json()["document_id"]
    recs = c.post(f"{V1}/dossiers/{did}/recommendations:extract").json()["reports"][0]["recommendations"]
    assert recs[0]["deadline"] == "D'ici à décembre 2023"
    assert [s["label"] for s in recs[0]["sub_points"]] == ["a", "b"]
    chunk = next(iter(repo.iter_chunks(did, [doc]))).id
    repo.save_findings(did, [Finding(id="fnd_1", dossier_id=did, severity="high", theme="t", validated=True,
                                     text="La Commission ne documentait pas ses besoins avant de recourir "
                                          "aux consultants externes.", source_ids=[chunk])])
    f = c.get(f"{V1}/dossiers/{did}/findings").json()[0]
    assert f["paragraph"] == 20 and f["recommendations"][0]["number"] == 1
    out = c.post(f"{V1}/dossiers/{did}/roadmap:generate", json={}).json()
    assert out["mode"] == "recommendations"
    items = out["roadmap"]["items"]
    assert len(items) == 2  # un par sous-point
    ini = items[0]["initiative"]
    assert ini["axis"].startswith("R1 — Compléter le cadre")
    assert ini["recommendation"]["label"] in ("a", "b")
    assert "Échéance fixée par le rapport" in ini["wave_reason"]
    assert "fnd_1" in [x for it in items for x in it["initiative"]["finding_ids"]]


def test_vagues_justifiees():
    today = date(2026, 11, 27)
    w, why = wave_for("D'ici à décembre 2023", 3, today)
    assert w == 1 and "dépassée" in why and "élevée" in why
    assert wave_for("D'ici à décembre 2023", 2, today)[0] == 2  # en retard : la gravité départage
    assert wave_for("juin 2027", 0, today)[0] == 2
    assert wave_for(None, 1, today)[0] == 3
