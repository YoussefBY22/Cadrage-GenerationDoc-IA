"""Lot 6 : l'assistant répond sans modèle sur l'aide de la page et l'état du dossier, avec sources sinon."""

V1 = "/api/v1"


def _dossier(c):
    return c.post(f"{V1}/dossiers", json={"name": "D", "client_name": "C"}).json()["id"]


def test_aide_de_la_page_sans_modele(client):
    did = _dossier(client)
    r = client.post(f"{V1}/dossiers/{did}/assistant",
                    json={"message": "À quoi sert cette page ?", "page_help": "Les constats du rapport."}).json()
    assert r == {"answer": "Les constats du rapport.", "sources": [], "model": False, "busy": []}


def test_etat_du_dossier_sans_modele(client):
    did = _dossier(client)
    r = client.post(f"{V1}/dossiers/{did}/assistant", json={"message": "Combien de constats ?"}).json()
    assert r["model"] is False and "0 constat" in r["answer"]


def test_question_libre_passe_par_le_modele(client):
    did = _dossier(client)
    r = client.post(f"{V1}/dossiers/{did}/assistant", json={"message": "Que dit le rapport sur la dépendance ?"})
    assert r.status_code == 200 and r.json()["model"] is True
