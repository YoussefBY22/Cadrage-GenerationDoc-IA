"""Recherche mixte branchée sur le dépôt réel ; un seul récupérateur (et son cache BM25) par appli."""

from fastapi import Request

from app.domain.retrieval import Passage, SearchQuery
from app.llm.base import LLMProvider
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reserve import reserve_diagnostic_places


class SearchService:
    def __init__(self, repo, provider: LLMProvider, pool: int = 50):
        self.retriever = HybridRetriever(repo, provider, pool=pool)

    def _roles(self, dossier_id: str) -> dict[str, str]:
        reader = getattr(self.retriever.repo, "document_roles", None)
        return reader(dossier_id) if reader else {}

    def search(self, dossier_id: str, texts: list[str], k: int = 10,
               document_ids: list[str] | None = None) -> list[Passage]:
        """Une trame n'est jamais une source ; les diagnostics ont des places réservées.

        Un filtre `document_ids` explicite est respecté tel quel.
        """
        roles = self._roles(dossier_id) if document_ids is None else {}
        allowed = ([d for d, r in roles.items() if r != "template"]
                   if "template" in roles.values() else document_ids)
        diag = {d for d, r in roles.items() if r == "diagnostic"}
        if not diag:
            return self.retriever.search(SearchQuery(
                dossier_id=dossier_id, texts=texts, k=k, document_ids=allowed))
        wide = self.retriever.search(SearchQuery(
            dossier_id=dossier_id, texts=texts, k=2 * k, document_ids=allowed))
        return reserve_diagnostic_places(wide, k, diag)

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
