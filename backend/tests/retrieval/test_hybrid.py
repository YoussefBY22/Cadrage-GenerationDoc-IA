import math

from app.domain.documents import Chunk
from app.domain.retrieval import Passage, SearchQuery
from app.llm.fake import FakeProvider, hash_embedding
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.rerank import NoopReranker


def _chunk(cid, doc, text, dossier="dos_1", ordinal=0):
    return Chunk(
        id=cid,
        document_id=doc,
        dossier_id=dossier,
        ordinal=ordinal,
        text=text,
        page_start=1,
        page_end=1,
        section_path=("S",),
        token_estimate=10,
    )


class MemSource:
    """Double en mémoire de Repository (iter_chunks, vector_search)."""

    def __init__(self, chunks, provider):
        self.chunks = chunks
        self.vecs = {c.id: provider.embed([c.text])[0] for c in chunks}
        self.iter_calls = 0

    def iter_chunks(self, dossier_id, document_ids=None):
        self.iter_calls += 1
        yield from self._iter(dossier_id, document_ids)

    def _iter(self, dossier_id, document_ids=None):
        for c in self.chunks:
            if c.dossier_id == dossier_id and (
                document_ids is None or c.document_id in document_ids
            ):
                yield c

    def vector_search(self, dossier_id, query, k, document_ids=None):
        scored = [
            (c.id, sum(a * b for a, b in zip(query, self.vecs[c.id], strict=True)))
            for c in self._iter(dossier_id, document_ids)
        ]
        return sorted(scored, key=lambda x: -x[1])[:k]


def _mk(chunks):
    p = FakeProvider()
    src = MemSource(chunks, p)
    return src, HybridRetriever(src, p)


CHUNKS = [
    _chunk("c1", "d1", "La gouvernance des données impose un comité de pilotage mensuel"),
    _chunk("c2", "d1", "Le budget prévisionnel atteint 1 250 euros par mois", ordinal=1),
    _chunk("c3", "d2", "Risque de dépendance envers un fournisseur unique de cloud"),
    _chunk("c4", "d2", "Formation des équipes métier au nouvel outil de reporting", ordinal=1),
    _chunk("x1", "d9", "Gouvernance du dossier voisin", dossier="dos_2"),
]


def test_labels_et_bm25_en_tete():
    _, r = _mk(CHUNKS)
    res = r.search(SearchQuery(dossier_id="dos_1", texts=["budget 1250 euros"], k=3))
    assert [p.label for p in res] == ["P1", "P2", "P3"]
    assert res[0].chunk.id == "c2"
    assert res[0].ranks["bm25"] == 1 and "vector" in res[0].ranks
    assert res[0].score > res[1].score


def test_vecteur_seul_retrouve_texte_identique():
    _, r = _mk(CHUNKS)
    q = "Risque de dépendance envers un fournisseur unique de cloud"
    assert r.search(SearchQuery(dossier_id="dos_1", texts=[q], k=1))[0].chunk.id == "c3"


def test_filtre_par_dossier_et_par_document():
    _, r = _mk(CHUNKS)
    res = r.search(SearchQuery(dossier_id="dos_1", texts=["gouvernance"], k=10))
    assert {p.chunk.id for p in res} <= {"c1", "c2", "c3", "c4"}
    res = r.search(SearchQuery(dossier_id="dos_2", texts=["gouvernance"], k=10))
    assert [p.chunk.id for p in res] == ["x1"]
    res = r.search(
        SearchQuery(dossier_id="dos_1", texts=["gouvernance"], k=10, document_ids=["d2"])
    )
    assert res and {p.chunk.document_id for p in res} == {"d2"}


def test_requetes_multiples_fusionnees():
    _, r = _mk(CHUNKS)
    res = r.search(
        SearchQuery(dossier_id="dos_1", texts=["comité pilotage", "fournisseur cloud"], k=4)
    )
    top2 = {p.chunk.id for p in res[:2]}
    assert top2 == {"c1", "c3"}


def test_diversite_par_document():
    chunks = [
        _chunk(f"a{i}", "dA", f"projet cadrage alpha {i} unique{i} " + "mot " * i, ordinal=i)
        for i in range(8)
    ] + [_chunk("b0", "dB", "projet cadrage beta")]
    _, r = _mk(chunks)
    res = r.search(SearchQuery(dossier_id="dos_1", texts=["projet cadrage"], k=4))
    from collections import Counter

    counts = Counter(p.chunk.document_id for p in res)
    assert max(counts.values()) <= math.ceil(4 / 2)
    assert "dB" in counts


def test_dedoublonnage_des_chevauchements():
    base = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"
    chunks = [
        _chunk("o1", "d1", base),
        _chunk("o2", "d1", base + " mike", ordinal=1),
        _chunk("o3", "d1", "tout autre sujet sans rapport vraiment", ordinal=2),
    ]
    _, r = _mk(chunks)
    res = r.search(SearchQuery(dossier_id="dos_1", texts=["alpha bravo charlie"], k=3))
    ids = [p.chunk.id for p in res]
    assert ("o1" in ids) != ("o2" in ids)


def test_cache_et_invalidation():
    src, r = _mk(CHUNKS)
    q = SearchQuery(dossier_id="dos_1", texts=["budget"], k=2)
    r.search(q)
    r.search(q)
    assert src.iter_calls == 1  # index BM25 construit une seule fois
    src.chunks.append(_chunk("n1", "d3", "nouveau exceptionnel", ordinal=0))
    src.vecs["n1"] = hash_embedding("nouveau exceptionnel")
    q2 = SearchQuery(dossier_id="dos_1", texts=["exceptionnel"], k=5)
    assert all("bm25" not in p.ranks for p in r.search(q2))  # index périmé
    r.invalidate("dos_1")
    res = r.search(q2)
    assert res[0].chunk.id == "n1" and res[0].ranks["bm25"] == 1
    assert src.iter_calls == 2


def test_reranker_appele_et_requete_vide():
    class Reverse:
        def rerank(self, query, passages):
            return list(reversed(passages))

    p = FakeProvider()
    r = HybridRetriever(MemSource(CHUNKS, p), p, reranker=Reverse())
    base = HybridRetriever(MemSource(CHUNKS, p), p, reranker=NoopReranker())
    q = SearchQuery(dossier_id="dos_1", texts=["budget gouvernance"], k=10)
    normal = [x.chunk.id for x in base.search(q)]
    assert [x.chunk.id for x in r.search(q)] == normal[::-1]
    assert base.search(SearchQuery(dossier_id="dos_1", texts=["  "], k=3)) == []
    assert isinstance(base.search(q)[0], Passage)
