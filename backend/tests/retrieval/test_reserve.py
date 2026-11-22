"""Places réservées aux diagnostics : promus quand pertinents, sans masquer les autres documents."""

from app.domain.documents import Chunk
from app.domain.retrieval import Passage
from app.retrieval.reserve import reserve_diagnostic_places, reserved_places


def P(n, doc):
    ch = Chunk(id=f"c{n}", document_id=doc, dossier_id="d", ordinal=n, text="t", page_start=1,
               page_end=1, section_path=(), token_estimate=1)
    return Passage(label=f"P{n}", chunk=ch, score=1.0, ranks={})


def test_reserved_places_is_a_third_min_one():
    assert [reserved_places(k) for k in (1, 3, 6, 10)] == [1, 1, 2, 3]


def test_diagnostic_is_promoted_and_others_keep_most_places():
    ranked = [P(i, "other") for i in range(1, 7)] + [P(7, "diag"), P(8, "diag")]
    out = reserve_diagnostic_places(ranked, 6, {"diag"}, reserved=2)
    assert len(out) == 6
    assert [p.chunk.id for p in out if p.chunk.document_id == "diag"] == ["c7", "c8"]
    assert sum(p.chunk.document_id == "other" for p in out) == 4  # rien n'est masqué en bloc
    assert [p.label for p in out] == [f"P{i}" for i in range(1, 7)]
    assert [p.chunk.id for p in out][:4] == ["c1", "c2", "c3", "c4"]  # l'ordre de rang est gardé


def test_nothing_changes_when_diagnostics_already_fill_their_places_or_are_absent():
    ranked = [P(1, "diag"), P(2, "other"), P(3, "other"), P(4, "other")]
    assert [p.chunk.id for p in reserve_diagnostic_places(ranked, 3, {"diag"}, reserved=1)] == [
        "c1", "c2", "c3"]
    ranked = [P(i, "other") for i in range(1, 5)]
    assert [p.chunk.id for p in reserve_diagnostic_places(ranked, 3, {"diag"})] == ["c1", "c2", "c3"]


def test_never_removes_a_diagnostic_passage():
    ranked = [P(1, "diag"), P(2, "diag"), P(3, "diag"), P(4, "diag")]
    out = reserve_diagnostic_places(ranked, 2, {"diag"}, reserved=2)
    assert [p.chunk.id for p in out] == ["c1", "c2"]
