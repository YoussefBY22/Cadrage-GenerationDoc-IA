"""Position et conflit : invite, schéma (ordre des propriétés) et appel vérifié."""

import pytest

from app.domain.documents import Chunk
from app.domain.retrieval import Passage
from app.generation.llm_schemas import LLMStance
from app.generation.prompting import build_stance_prompt
from app.llm.fake import FakeProvider
from app.services import stance


def _passages():
    texts = ["La Commission devrait recruter davantage de contrôleurs d'ici fin 2026.",
             "La stratégie prévoit 50 recrutements par an, sans dépasser ce plafond."]
    return [Passage(label=f"P{i}", score=1.0, ranks={}, chunk=Chunk(
        id=f"c{i}", document_id="d", dossier_id="x", ordinal=i, text=t, page_start=None, page_end=None,
        section_path=(), token_estimate=20)) for i, t in enumerate(texts, 1)]


def test_schema_order_puts_stance_before_sentences():
    assert list(LLMStance.model_json_schema()["properties"]) == ["status", "stance", "sentences", "missing_evidence"]


def test_prompt_per_mode():
    ps = _passages()
    pos = build_stance_prompt("position", ps, nonce="n1")
    con = build_stance_prompt("conflict", ps, nonce="n1")
    assert "partial" in pos and "DEUX" not in pos
    assert "conflict" in con and "DEUX" in con and "<<PASSAGE id=P2 nonce=n1>>" in con
    with pytest.raises(ValueError):
        build_stance_prompt("autre", ps, nonce="n1")


def test_assess_verifies_each_justification():
    ps = _passages()

    def handler(prompt, schema):
        assert schema is LLMStance
        return {"status": "ok", "stance": "conflict", "sentences": [
            {"text": "La stratégie prévoit 50 recrutements par an, sans dépasser ce plafond.", "kind": "fact",
             "sources": ["P2"]},
            {"text": "La Commission devrait recruter davantage de contrôleurs d'ici fin 2026.", "kind": "fact",
             "sources": ["P1"]}]}

    out = stance.assess(FakeProvider(handler=handler), "conflict", ps, dossier_id="x")
    assert out["stance"] == "conflict" and len(out["sentences"]) == 2
    assert not [i for i in out["report"]["issues"] if i["severity"] == "blocking"]
