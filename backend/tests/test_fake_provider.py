import pytest
from pydantic import BaseModel

from app.llm import FakeProvider, LLMError


class Sentence(BaseModel):
    text: str
    source_ids: list[str]


class Section(BaseModel):
    title: str
    status: str
    sentences: list[Sentence]
    score: float | None = None


def test_generate_is_deterministic():
    a, b = FakeProvider(), FakeProvider()
    assert a.generate("bonjour") == b.generate("bonjour")
    assert a.generate("bonjour") != a.generate("au revoir")


def test_structured_default_is_valid_and_deterministic():
    one = FakeProvider().generate_structured("x", Section)
    two = FakeProvider().generate_structured("x", Section)
    assert one == two
    assert len(one.sentences) >= 1


def test_script_overrides_answer():
    p = FakeProvider(script=[("SECTION-A", {"title": "T", "status": "ok", "sentences": []})])
    out = p.generate_structured("génère SECTION-A", Section)
    assert out.title == "T" and out.sentences == []


def test_invalid_scripted_answer_raises():
    p = FakeProvider(script=[("X", {"title": 1})])
    with pytest.raises(LLMError):
        p.generate_structured("X", Section)


def test_embeddings_deterministic_normalized_and_similar():
    p = FakeProvider()
    v1, v2, v3 = p.embed(["budget du projet", "budget du projet pilote", "ciel bleu océan"])
    assert len(v1) == p.embedding_dimension
    assert p.embed(["budget du projet"])[0] == v1
    def dot(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert abs(dot(v1, v1) - 1.0) < 1e-9
    assert dot(v1, v2) > dot(v1, v3)


def test_calls_are_recorded():
    p = FakeProvider()
    p.generate("a")
    assert p.calls[0]["kind"] == "generate"
