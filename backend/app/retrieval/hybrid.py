"""Recherche mixte BM25 + vecteurs fusionnés par RRF, avec diversité et dédoublonnage."""

import math
from collections.abc import Iterator
from typing import Protocol

from app.domain.documents import Chunk
from app.domain.retrieval import Passage, SearchQuery
from app.llm.base import LLMProvider

from .bm25 import BM25Index
from .chunking import indexed_text
from .fusion import rrf
from .rerank import NoopReranker, Reranker
from .textnorm import tokenize

RERANK_TOP = 30
OVERLAP_LIMIT = 0.5
SHINGLE = 5


class ChunkSource(Protocol):
    """Sous-ensemble de Repository utilisé ici (mêmes signatures)."""

    def iter_chunks(
        self, dossier_id: str, document_ids: list[str] | None = None
    ) -> Iterator[Chunk]: ...

    def vector_search(
        self, dossier_id: str, query: list[float], k: int, document_ids: list[str] | None = None
    ) -> list[tuple[str, float]]: ...


def _shingles(text: str) -> set[tuple[str, ...]]:
    words = text.lower().split()
    if len(words) <= SHINGLE:
        return {tuple(words)}
    return {tuple(words[i : i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}


def _overlaps(a: Chunk, b: Chunk) -> bool:
    """Vrai si un passage recouvre plus de 50 % du plus petit des deux (même document)."""
    if a.document_id != b.document_id:
        return False
    sa, sb = _shingles(a.text), _shingles(b.text)
    return len(sa & sb) / max(1, min(len(sa), len(sb))) > OVERLAP_LIMIT


class HybridRetriever:
    def __init__(
        self,
        repo: ChunkSource,
        provider: LLMProvider,
        reranker: Reranker | None = None,
        pool: int = 50,
    ):
        self.repo = repo
        self.provider = provider
        self.reranker: Reranker = reranker or NoopReranker()
        self.pool = pool
        self._cache: dict[str, tuple[BM25Index, dict[str, Chunk]]] = {}

    def invalidate(self, dossier_id: str) -> None:
        """À appeler après toute ingestion ou suppression dans le dossier."""
        self._cache.pop(dossier_id, None)

    def _index(self, dossier_id: str) -> tuple[BM25Index, dict[str, Chunk]]:
        if dossier_id not in self._cache:
            index = BM25Index()
            chunks: dict[str, Chunk] = {}
            for chunk in self.repo.iter_chunks(dossier_id):
                chunks[chunk.id] = chunk
                index.add(chunk.id, tokenize(indexed_text(chunk)))
            self._cache[dossier_id] = (index, chunks)
        return self._cache[dossier_id]

    def search(self, q: SearchQuery) -> list[Passage]:
        texts = [t for t in q.texts if t.strip()]
        if not texts or q.k <= 0:
            return []
        index, chunks = self._index(q.dossier_id)
        allowed = set(q.document_ids) if q.document_ids is not None else None

        def ok(cid: str) -> bool:
            return cid in chunks and (allowed is None or chunks[cid].document_id in allowed)

        rankings: list[list[str]] = []
        sources: list[str] = []
        vectors = self.provider.embed(texts)
        for text, vec in zip(texts, vectors, strict=True):
            hits = index.search(tokenize(text), len(chunks))
            rankings.append([cid for cid, _ in hits if ok(cid)][: self.pool])
            sources.append("bm25")
            vhits = self.repo.vector_search(q.dossier_id, vec, self.pool, q.document_ids)
            rankings.append([cid for cid, _ in vhits if ok(cid)])
            sources.append("vector")

        best: dict[str, dict[str, int]] = {}
        for source, ranking in zip(sources, rankings, strict=True):
            for rank, cid in enumerate(ranking, start=1):
                ranks = best.setdefault(cid, {})
                ranks[source] = min(rank, ranks.get(source, rank))

        candidates = [
            Passage(label="", chunk=chunks[cid], score=score, ranks=best[cid])
            for cid, score in rrf(rankings)
        ]
        head = self.reranker.rerank(texts[0], candidates[:RERANK_TOP])
        candidates = [*head, *candidates[RERANK_TOP:]]

        cap = math.ceil(q.k / 2)
        per_doc: dict[str, int] = {}
        selected: list[Passage] = []
        for cand in candidates:
            if len(selected) >= q.k:
                break
            doc = cand.chunk.document_id
            if per_doc.get(doc, 0) >= cap:
                continue
            if any(_overlaps(cand.chunk, s.chunk) for s in selected):
                continue
            per_doc[doc] = per_doc.get(doc, 0) + 1
            selected.append(cand)
        return [p.model_copy(update={"label": f"P{i}"}) for i, p in enumerate(selected, start=1)]
