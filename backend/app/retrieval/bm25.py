"""BM25 (Okapi, idf de type Lucene) maison, en mémoire."""

import math
from collections import Counter


class BM25Index:
    """Index inversé BM25. Les égalités de score sont départagées par ordre d'ajout."""

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._ids: list[str] = []
        self._lengths: list[int] = []
        self._postings: dict[str, list[tuple[int, int]]] = {}  # terme -> [(doc, tf)]
        self._total_len = 0

    def __len__(self) -> int:
        return len(self._ids)

    def add(self, chunk_id: str, tokens: list[str]) -> None:
        doc = len(self._ids)
        self._ids.append(chunk_id)
        self._lengths.append(len(tokens))
        self._total_len += len(tokens)
        for term, tf in Counter(tokens).items():
            self._postings.setdefault(term, []).append((doc, tf))

    def idf(self, term: str) -> float:
        n = len(self._postings.get(term, ()))
        return math.log(1 + (len(self._ids) - n + 0.5) / (n + 0.5))

    def search(self, tokens: list[str], k: int) -> list[tuple[str, float]]:
        """Renvoie jusqu'à k couples (chunk_id, score > 0), meilleur d'abord."""
        if not self._ids or k <= 0:
            return []
        avgdl = self._total_len / len(self._ids) or 1.0
        scores: dict[int, float] = {}
        for term in set(tokens):
            idf = self.idf(term)
            for doc, tf in self._postings.get(term, ()):
                norm = self.k1 * (1 - self.b + self.b * self._lengths[doc] / avgdl)
                scores[doc] = scores.get(doc, 0.0) + idf * tf * (self.k1 + 1) / (tf + norm)
        ranked = sorted(((d, s) for d, s in scores.items() if s > 0), key=lambda x: (-x[1], x[0]))
        return [(self._ids[d], s) for d, s in ranked[:k]]
