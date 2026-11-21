"""Réordonnancement optionnel des passages."""

from typing import Protocol

from app.domain.retrieval import Passage


class Reranker(Protocol):
    def rerank(self, query: str, passages: list[Passage]) -> list[Passage]: ...


class NoopReranker:
    """Ne change rien (défaut)."""

    def rerank(self, query: str, passages: list[Passage]) -> list[Passage]:
        return list(passages)
