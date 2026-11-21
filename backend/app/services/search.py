"""Recherche mixte branchée sur le dépôt réel ; un seul récupérateur (et son cache BM25) par appli."""

from fastapi import Request

from app.domain.retrieval import Passage, SearchQuery
from app.llm.base import LLMProvider
from app.retrieval.hybrid import HybridRetriever


class SearchService:
    def __init__(self, repo, provider: LLMProvider, pool: int = 50):
        self.retriever = HybridRetriever(repo, provider, pool=pool)

    def search(self, dossier_id: str, texts: list[str], k: int = 10,
               document_ids: list[str] | None = None) -> list[Passage]:
        return self.retriever.search(
            SearchQuery(dossier_id=dossier_id, texts=texts, k=k, document_ids=document_ids))

    def invalidate(self, dossier_id: str) -> None:
        """À appeler après toute ingestion : le cache BM25 du dossier est reconstruit au besoin."""
        self.retriever.invalidate(dossier_id)


def get_search_service(request: Request) -> SearchService:
    """Service partagé, créé au premier besoin sur le dépôt et le fournisseur de l'appli."""
    from app.api.deps import get_repo
    from app.config import get_settings

    state = request.app.state
    if getattr(state, "search_service", None) is None:
        state.search_service = SearchService(
            get_repo(request), state.provider, pool=get_settings().retrieval_pool)
    return state.search_service
