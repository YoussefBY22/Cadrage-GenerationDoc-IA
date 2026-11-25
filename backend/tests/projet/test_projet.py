"""Fiche projet, recommandations des rapports d'audit (règles + contrôle de cohérence), registre des entraînements."""

import io
import json
from pathlib import Path

from PIL import Image

from app.services import projet

V1 = "/api/v1"
RAPPORT = ("Rapport spécial\n\nConclusions et recommandations\n\n"
           "Recommandation n° 1 – Compléter le cadre en place régissant le recours aux consultants. "
           "La Commission devrait développer son cadre.\n\n"
           "Recommandation n° 2 – Améliorer la surveillance des risques La Commission devrait améliorer.\n\n"
           "Recommandation n° 4 – Améliorer l'information relative aux services La Commission devrait rendre compte.\n\n"
           "Voir aussi les recommandations 1 à 4 ci-dessus.\n")


def _dossier(client) -> str:
    return client.post(f"{V1}/dossiers", json={"name": "D", "client_name": "C"}).json()["id"]


def _rapport(client, did, texte=RAPPORT, nom="rapport.txt") -> str:
    r = client.post(f"{V1}/dossiers/{did}/documents", files={"file": (nom, texte.encode())})
    assert r.status_code == 201, r.text
    doc = r.json().get("id") or r.json()["document_id"]
    assert client.patch(f"{V1}/documents/{doc}", json={"role": "diagnostic"}).status_code == 200
    return doc


def test_detecter_titres_et_numeros_cites():
    titres, cites = projet.detecter([("c1", 42, RAPPORT)])
    assert [t["number"] for t in titres] == [1, 2, 4]
    assert titres[1]["title"] == "Améliorer la surveillance des risques"
    assert titres[0]["title"].startswith("Compléter le cadre")
    assert cites == [1, 2, 3, 4]


def test_controle_trou_doublon_et_non_detecte():
    actives = [{"number": 1}, {"number": 2}, {"number": 2}]
    c = projet.controle([1, 2, 3], actives, True, False)
    assert c["status"] == "ecart" and c["missing"] == [3] and c["duplicates"] == [2] and c["expected"] == 3
    assert projet.controle([], [], True, False)["status"] == "non_detectees"
    assert projet.controle([], [], True, True)["status"] == "ok"
    assert projet.controle([1], [{"number": 1}], True, False)["status"] == "ok"


def test_extraction_puis_corrections_du_consultant(client):
    did = _dossier(client)
    doc = _rapport(client, did)
    out = client.post(f"{V1}/dossiers/{did}/recommendations:extract").json()
    (rap,) = out["reports"]
    assert [r["number"] for r in rap["recommendations"]] == [1, 2, 4]
    assert rap["check"] == {"status": "ecart", "expected": 4, "extracted": 3, "missing": [3], "duplicates": []}
    assert out["alerts"] == 1
    # le consultant ajoute la n° 3 oubliée : plus d'écart
    r = client.post(f"{V1}/dossiers/{did}/recommendations",
                    json={"document_id": doc, "title": "Mieux exploiter les résultats", "number": 3, "page": 44})
    assert r.status_code == 201 and r.json()["origin"] == "consultant"
    vue = client.get(f"{V1}/dossiers/{did}/recommendations").json()
    assert vue["reports"][0]["check"]["status"] == "ok" and vue["alerts"] == 0
    recs = {x["number"]: x for x in vue["reports"][0]["recommendations"]}
    # valider, puis fusionner un doublon, puis supprimer
    assert client.patch(f"{V1}/recommendations/{recs[1]['id']}", json={"status": "validated"}).json()["status"] == "validated"
    doublon = client.post(f"{V1}/dossiers/{did}/recommendations",
                          json={"document_id": doc, "title": "Doublon", "number": 2}).json()
    assert client.get(f"{V1}/dossiers/{did}/recommendations").json()["reports"][0]["check"]["duplicates"] == [2]
    m = client.patch(f"{V1}/recommendations/{doublon['id']}", json={"merge_into": recs[2]["id"]}).json()
    assert m["status"] == "merged" and m["merged_into"] == recs[2]["id"]
    assert client.patch(f"{V1}/recommendations/{recs[4]['id']}", json={"status": "deleted"}).status_code == 200
    vue = client.get(f"{V1}/dossiers/{did}/recommendations").json()["reports"][0]["check"]
    assert vue["missing"] == [4] and vue["duplicates"] == []
    # une nouvelle extraction ne défait pas les corrections
    vue = client.post(f"{V1}/dossiers/{did}/recommendations:extract").json()["reports"][0]
    assert {r["number"]: r["status"] for r in vue["recommendations"] if r["origin"] == "rules"}[4] == "deleted"
    assert client.patch(f"{V1}/recommendations/{recs[1]['id']}", json={"merge_into": recs[1]["id"]}).status_code == 422


def test_rapport_sans_numerotation_jamais_zero_silencieux(client):
    did = _dossier(client)
    doc = _rapport(client, did, "Rapport\n\nNous avons observé des retards importants dans les paiements.\n")
    out = client.post(f"{V1}/dossiers/{did}/recommendations:extract").json()
    assert out["reports"][0]["check"]["status"] == "non_detectees" and out["alerts"] == 1
    out = client.put(f"{V1}/dossiers/{did}/reports/{doc}/no-recommendation", json={"value": True}).json()
    assert out["reports"][0]["check"]["status"] == "ok" and out["alerts"] == 0


def test_fiche_projet_et_logo(client):
    did = _dossier(client)
    p = client.get(f"{V1}/dossiers/{did}/profile").json()
    assert p["client_request"] == "" and p["logo"] is None and p["documents"] == 0
    r = client.put(f"{V1}/dossiers/{did}/profile", json={
        "client_name": "Ministère", "client_request": "Mettre en œuvre les recommandations. Le reste suit.",
        "start_date": "2026-09-01", "end_date": "2026-12-15"})
    assert r.status_code == 200
    assert r.json()["request_summary"] == "Mettre en œuvre les recommandations." and r.json()["client_name"] == "Ministère"
    assert client.put(f"{V1}/dossiers/{did}/profile", json={"end_date": "2026-01-01"}).status_code == 422
    img = Image.new("RGB", (1200, 800), (40, 40, 56))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    r = client.post(f"{V1}/dossiers/{did}/profile/logo", files={"file": ("logo.png", buf.getvalue())})
    assert r.status_code == 200 and r.json()["logo"].startswith("data:image/png;base64,")
    assert len(r.json()["logo"]) < 140_000
    assert client.post(f"{V1}/dossiers/{did}/profile/logo",
                       files={"file": ("x.png", b"pas une image")}).status_code == 422
    assert client.put(f"{V1}/dossiers/{did}/profile", json={"clear_logo": True}).json()["logo"] is None
    assert client.get(f"{V1}/dossiers/dos_inconnu/profile").status_code == 404


def test_registre_des_entrainements(repo, client):
    dossier = Path(__file__).resolve().parents[3] / "training" / "registre"
    for f in sorted(dossier.glob("*.json")):
        projet.import_training(repo.engine, json.loads(f.read_text(encoding="utf-8")))
    runs = {r["id"]: r for r in client.get(f"{V1}/trainings").json()}
    assert set(runs) == {"essai1", "v4", "v5"}
    assert (runs["v4"]["best_step"], runs["v4"]["best_val_loss"], runs["v4"]["adopted"]) == (80, 0.165, True)
    assert (runs["v5"]["best_step"], runs["v5"]["best_val_loss"], runs["v5"]["stop_step"]) == (120, 0.155, 160)
    assert runs["essai1"]["validation"] == [] and runs["essai1"]["best_val_loss"] == 0.255
    # réimporter remplace
    projet.import_training(repo.engine, json.loads((dossier / "v4.json").read_text(encoding="utf-8")))
    assert len(client.get(f"{V1}/trainings").json()) == 3
