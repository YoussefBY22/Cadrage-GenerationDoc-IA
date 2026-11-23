"""Fenêtre de contexte : rien n'est coupé en silence, rien de non lu n'est citable."""

import json

import httpx

from app.domain.documents import Chunk
from app.domain.retrieval import Passage
from app.generation import prompting
from app.llm.ollama import OllamaProvider


def _passages(n, words=300):
    return [Passage(label=f"P{i}", score=0.0, ranks={}, chunk=Chunk(
        id=f"c{i}", document_id="d", dossier_id="x", ordinal=i, text="mot " * words,
        page_start=None, page_end=None, section_path=(), token_estimate=words))
        for i in range(1, n + 1)]


def test_tous_les_passages_sont_lus_une_fois():
    ps = _passages(23)
    lots = prompting.batch_passages(ps, "n", 1500, 8)
    assert [p.chunk.id for lot in lots for p in lot] == [p.chunk.id for p in ps]
    assert len(lots) > 3


def test_citable_egale_envoye():
    ps = _passages(10)
    sent = prompting.fit_passages(ps, "n", 1500)
    text = prompting.render_passages(ps, "n", 1500)
    assert 0 < len(sent) < len(ps)
    assert all((f"id={p.label} " in text) == (p in sent) for p in ps)


def test_estimation_majore_la_mesure_reelle():
    phrase = "Le comité de pilotage examine chaque trimestre l'avancement des chantiers et les risques associés. "
    assert prompting.safe_tokens(phrase * 85) >= 1998  # 1 190 mots = 1 998 jetons mesurés sur qwen3:4b


def test_budget_laisse_la_place_a_la_reponse():
    fixed = "mot " * 400
    b = prompting.passage_budget(4096, fixed, 700)
    assert b + prompting.safe_tokens(fixed) + 700 <= 4096


def test_ollama_refuse_au_lieu_de_couper():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "ok"}})

    provider = OllamaProvider("http://localhost:11434", "m", "e", {"localhost"},
                              client=httpx.Client(transport=httpx.MockTransport(handler)))
    provider.generate("bonjour")
    assert seen["truncate"] is False and seen["shift"] is False
    assert seen["options"]["num_ctx"] == provider.context_tokens == 4096
