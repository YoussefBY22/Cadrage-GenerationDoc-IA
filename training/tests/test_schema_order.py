"""L'ordre des propriétés d'une réponse d'entraînement doit être celui du schéma envoyé à Ollama."""

from __future__ import annotations

import json

import pytest
from app.generation.llm_schemas import LLMFindings, LLMSection

from training.dataset import schema_order


def _keys(model) -> list[str]:
    return list(model.model_json_schema()["properties"])


def test_section_schema_order_is_the_one_ollama_enforces():
    # status, sentences, missing_evidence : c'est CET ordre que la grammaire impose.
    assert _keys(LLMSection) == ["status", "sentences", "missing_evidence"]


def test_ordered_follows_the_schema_not_the_writer():
    bad = {"status": "ok", "missing_evidence": None,
           "sentences": [{"findings": [], "sources": ["P1"], "kind": "fact", "text": "t"}]}
    good = schema_order.ordered(LLMSection, bad)
    assert list(good) == ["status", "sentences", "missing_evidence"]
    assert list(good["sentences"][0]) == _keys(type(LLMSection.model_validate(bad).sentences[0]))[:4]
    assert not schema_order.is_ordered(LLMSection, bad)
    assert schema_order.is_ordered(LLMSection, good)


def test_refusal_and_findings_are_ordered():
    refus = json.loads(schema_order.dumps(LLMSection, {"missing_evidence": "x", "sentences": [], "status": "insufficient_evidence"}))
    assert list(refus) == ["status", "sentences", "missing_evidence"]
    f = json.loads(schema_order.dumps(LLMFindings, {"findings": [{"sources": ["P1"], "severity": "low", "theme": "a", "text": "t"}],
                                                   "status": "ok"}))
    assert list(f) == ["status", "findings"] and list(f["findings"][0]) == ["text", "theme", "severity", "sources"]


def test_unknown_property_is_refused():
    with pytest.raises(ValueError):
        schema_order.ordered(LLMSection, {"status": "ok", "inconnue": 1})
