"""Audit de la PR 18 sur qwen3:4b réel : les quatre défauts mesurés, chacun reproduit ici."""

from app.llm import FakeProvider
from app.services import decisions as dec
from app.services import generation
from tests.api.test_context_chat import _ask, _chat_handler, _dossier
from tests.services.test_decisions import _decide, _prepare
from tests.services.test_generation import USER
from tests.services.test_generation_fakes import best_sentence, honest, passages_of

PROFIL = "Consultant senior justifiant de dix ans d'expérience en conduite de projets."
CALENDRIER = "Mission de douze semaines à partir de janvier 2027."


def copier(prompt, schema):
    """Le qwen3:4b mesuré : recopie le diagnostic et ne cite jamais D1."""
    if schema.__name__ != "LLMSection":
        return honest(prompt, schema)
    label, text = passages_of(prompt)[0]
    return {"status": "ok", "sentences": [
        {"text": best_sentence(text), "kind": "fact", "sources": [label]}]}


def triche(prompt, schema):
    """Le contenu d'une décision, cité comme un passage du diagnostic (fausse attribution)."""
    if schema.__name__ != "LLMSection":
        return honest(prompt, schema)
    label, _ = passages_of(prompt)[0]
    return {"status": "ok", "sentences": [
        {"text": "Mission de douze semaines à partir de janvier 2027.", "kind": "fact",
         "sources": [label]},
        {"text": "Un consultant ayant dix ans d'expérience.", "kind": "fact", "sources": [label]}]}


# --- 1. une section de décision est rendue depuis les décisions, sans modèle ----------------------
def test_section_de_decision_rendue_telle_quelle_sans_appel(repo, tmp_path):
    p, did, search, st, dl = _prepare(repo, tmp_path, copier)
    d = _decide(repo, did, "profile", PROFIL)
    r = generation.generate_section(repo, p, search, dl, "profil", USER, settings=st)
    assert p.calls == []  # le modèle n'a pas pu recopier les constats
    sent = r["section"]["sentences"]
    assert [s["text"] for s in sent] == [PROFIL] and sent[0]["decision_ids"] == [d.id]
    assert sent[0]["source_ids"] == [] and r["status"] == "ok" and r["tpv"] == 1.0


def test_plusieurs_decisions_de_la_categorie_toutes_rendues(repo, tmp_path):
    p, did, search, st, dl = _prepare(repo, tmp_path, copier)
    a = _decide(repo, did, "schedule", CALENDRIER)
    b = _decide(repo, did, "schedule", "Remise du rapport final fin mars 2027.")
    _decide(repo, did, "budget", "Enveloppe de quarante mille euros.")  # autre catégorie : absente
    r = generation.generate_section(repo, p, search, dl, "calendrier", USER, settings=st)
    assert [s["decision_ids"] for s in r["section"]["sentences"]] == [[a.id], [b.id]]
    assert p.calls == []


# --- 2. fausse attribution : le contenu d'une décision cité comme un passage ----------------------
def test_contenu_de_decision_cite_comme_passage_bloque(repo, tmp_path):
    p, did, search, st, dl = _prepare(repo, tmp_path, triche)
    _decide(repo, did, "schedule", CALENDRIER)
    _decide(repo, did, "profile", PROFIL)
    r = generation.generate_section(repo, p, search, dl, "contexte", USER, settings=st)
    blocking = [i for i in r["report"]["issues"] if i["severity"] == "blocking"]
    assert {i["sentence_index"] for i in blocking} == {0, 1}  # y compris « dix ans » en lettres
    faux = {i["sentence_index"] for i in blocking
            if i["code"] == "FOREIGN_SOURCE" and "décision humaine" in i["detail"]}
    assert faux == {0, 1}  # nommé « faux ancrage », pas seulement « nombre absent »


def test_phrase_du_diagnostic_non_touchee_par_le_controle(repo, tmp_path):
    p, did, search, st, dl = _prepare(repo, tmp_path, copier)
    _decide(repo, did, "schedule", CALENDRIER)
    r = generation.generate_section(repo, p, search, dl, "contexte", USER, settings=st)
    assert r["tpv"] == 1.0 and not r["report"]["issues"]


# --- 3. chat : champs vides ignorés sans bruit, une proposition valide confirmable ---------------
def test_chat_champs_vides_ignores_et_proposition_valide(client, provider):
    did = _dossier(client)
    provider.handler = _chat_handler(
        reply="Je note le périmètre.",
        fields=[{"field": "sector", "value": ""}, {"field": "size", "value": " "},
                {"field": "country", "value": ""},
                {"field": "scope", "value": "Refonte du processus de paie"}],
        decisions=[{"category": "schedule", "text": "Mission de douze semaines."}])
    out = _ask(client, did, "La mission dure douze semaines pour la refonte du processus de paie.")
    assert [f["field"] for f in out["proposals"]["fields"]] == ["scope"]
    assert [d["category"] for d in out["proposals"]["decisions"]] == ["schedule"]
    assert out["dropped"] == []  # les champs vides ne font aucun bruit
    # confirmable : la fiche reçoit le champ, la décision est créée puis confirmée
    scope = out["proposals"]["fields"][0]
    r = client.put(f"/api/v1/dossiers/{did}/context", json={scope["field"]: scope["value"]})
    assert r.json()["data"]["scope"] == "Refonte du processus de paie"
    prop = out["proposals"]["decisions"][0]
    created = client.post(f"/api/v1/dossiers/{did}/decisions",
                          json={"category": prop["category"], "text": prop["text"]}).json()
    assert client.post(f"/api/v1/decisions/{created['id']}:confirm").json()["status"] == "confirmed"


def test_chat_prompt_liste_champs_et_categories_et_donne_un_exemple(client, provider):
    did = _dossier(client)
    provider.handler = _chat_handler()
    _ask(client, did, "Bonjour")
    sys_, prompt = provider.calls[-1]["system"], provider.calls[-1]["prompt"]
    assert "omets" in sys_.lower()
    for token in ("sector", "project_types", "budget", "schedule", "EXEMPLE"):
        assert token in prompt


# --- 4. une décision se crée « proposée » ; la confirmation est une étape distincte ---------------
def test_creation_directe_confirmee_refusee(client):
    did = _dossier(client)
    r = client.post(f"/api/v1/dossiers/{did}/decisions",
                    json={"category": "budget", "text": "40 000 euros", "status": "confirmed"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "CREATE_AS_PROPOSED"
    ok = client.post(f"/api/v1/dossiers/{did}/decisions",
                     json={"category": "budget", "text": "40 000 euros"}).json()
    assert ok["status"] == "proposed" and ok["confirmed_at"] is None
    assert client.post(f"/api/v1/decisions/{ok['id']}:confirm").json()["status"] == "confirmed"


def test_service_refuse_aussi_la_creation_confirmee(repo):
    import pytest

    from app.services.generation import GenerationError

    did = repo.create_dossier("D", "C", "fr", "usr_dev")
    with pytest.raises(GenerationError):
        dec.create(repo, did, USER, category="budget", text="x", status="confirmed")
    assert FakeProvider  # import utilisé : le faux modèle reste le seul fournisseur des tests
