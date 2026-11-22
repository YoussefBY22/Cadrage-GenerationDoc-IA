"""Test de fumée contre un VRAI Ollama local (sauté si le serveur ou les modèles sont absents)."""

import os

import httpx
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.llm import build_provider

pytestmark = pytest.mark.ollama

URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
GEN = os.environ.get("OLLAMA_GENERATION_MODEL", "qwen3:4b")
EMB = os.environ.get("OLLAMA_EMBEDDING_MODEL", "bge-m3")


def _installed() -> set[str]:
    try:
        r = httpx.get(f"{URL}/api/tags", timeout=3, trust_env=False)
        return {m["name"] for m in r.json()["models"]}
    except (httpx.HTTPError, ValueError, KeyError):
        return set()


@pytest.fixture(scope="module")
def provider():
    have = _installed()
    if not any(n.split(":")[0] == GEN.split(":")[0] for n in have) \
            or not any(n.split(":")[0] == EMB.split(":")[0] for n in have):
        pytest.skip("Ollama absent ou modèles non installés")
    return build_provider(Settings(llm_provider="ollama", ollama_base_url=URL,
                                   ollama_generation_model=GEN, ollama_embedding_model=EMB,
                                   llm_timeout_seconds=300))


class Answer(BaseModel):
    capitale: str
    pays: str


def test_structured_output_without_thinking(provider):
    out = provider.generate_structured("Quelle est la capitale de la France ? Réponds en JSON.",
                                       Answer)
    assert "paris" in out.capitale.lower()


def test_generate_has_no_think_block(provider):
    text = provider.generate("Dis bonjour en un mot.", max_tokens=200)
    assert text.strip() and "<think>" not in text


def test_embeddings_dimension_1024(provider):
    vecs = provider.embed(["recherche d'information", "information retrieval"])
    assert len(vecs) == 2 and provider.embedding_dimension == 1024
