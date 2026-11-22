"""Porte de pertinence : seuil par modèle, refus avant l'appel au modèle."""

from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.generation.relevance import below_threshold, resolve_threshold
from app.llm import FakeProvider
from app.main import create_app
from tests.generation.test_en_parcours import DOCS, P
from tests.services.test_generation_fakes import honest


def _search(*scores):
    class Retriever:
        provider = NS(embed=lambda texts: [[0.0]] * len(texts))
        repo = NS(vector_search=lambda d, v, k: [("c", scores[0])] if scores else [])

    return NS(retriever=Retriever())


def test_seuil_par_modele_et_reglage():
    assert resolve_threshold(NS(relevance_threshold=None, llm_provider="fake")) == 0.0
    assert resolve_threshold(NS(relevance_threshold=None, llm_provider="ollama",
                                ollama_embedding_model="bge-m3:latest")) == 0.45
    assert resolve_threshold(NS(relevance_threshold=None, llm_provider="ollama",
                                ollama_embedding_model="autre")) == 0.0
    assert resolve_threshold(NS(relevance_threshold=0.6, llm_provider="fake")) == 0.6
    assert resolve_threshold(NS(relevance_threshold=0, llm_provider="ollama",
                                ollama_embedding_model="bge-m3")) == 0.0


def test_porte():
    assert below_threshold(_search(0.40), "d", ["q"], 0.45) == (True, 0.40)
    assert below_threshold(_search(0.50), "d", ["q"], 0.45) == (False, 0.50)
    assert below_threshold(_search(0.10), "d", ["q"], 0) == (False, None)  # désactivée
    assert below_threshold(_search(), "d", ["q"], 0.45) == (True, None)  # aucun passage
    assert below_threshold(_search(0.9), "d", [" "], 0.45) == (True, None)  # aucune requête


@pytest.fixture
def api(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "2")  # un cosinus ne dépasse pas 1 : tout est refusé
    get_settings.cache_clear()
    calls = []

    def handler(prompt, schema):
        calls.append(schema.__name__)
        return honest(prompt, schema)

    with TestClient(create_app(FakeProvider(handler=handler), repo)) as c:
        c.calls = calls
        yield c
    get_settings.cache_clear()


def test_section_refusee_sans_appel_au_modele(api):
    did = api.post(f"{P}/dossiers", json={"name": "D", "client_name": "C", "language": "en"}).json()["id"]
    for name, body in DOCS:
        assert api.post(f"{P}/dossiers/{did}/documents", files={"file": (name, body.encode())}).status_code == 201
    tid = api.post(f"{P}/dossiers/{did}/deliverables", json={"type": "tor"}).json()["deliverable_id"]
    before = len(api.calls)
    r = api.post(f"{P}/deliverables/{tid}/sections/contexte:generate")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "refused" and r.json()["section"]["status"] == "insufficient_evidence"
    assert "assez proche" in r.json()["section"]["missing_evidence"]
    assert len(api.calls) == before  # aucun appel au modèle
