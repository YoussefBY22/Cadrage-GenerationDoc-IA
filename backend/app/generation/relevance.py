"""Porte de pertinence : refuser une section AVANT l'appel au modèle si rien de proche n'a été trouvé.

Le score est le meilleur cosinus (requêtes de la section × passages du dossier) : contrairement au score de
fusion RRF, qui ne dépend que des rangs (le premier passage a toujours ~0,03), il reflète la proximité réelle.
Seuils calibrés sur le corpus or avec bge-m3 (voir docs/lots/Q2.md) ; ils dépendent du modèle d'embeddings.
"""

from __future__ import annotations

# Seuil par modèle d'embeddings (0 = porte désactivée). bge-m3 : « sans preuve » ≤ 0,43 ; « preuve » ≥ 0,535.
DEFAULT_THRESHOLDS: dict[str, float] = {"bge-m3": 0.45}


def resolve_threshold(settings) -> float:
    """Seuil explicite (RELEVANCE_THRESHOLD) sinon celui du modèle d'embeddings réel ; 0 = désactivée."""
    explicit = getattr(settings, "relevance_threshold", None)
    if explicit is not None:
        return float(explicit)
    if getattr(settings, "llm_provider", "fake") != "ollama":
        return 0.0  # embeddings factices (tests, démo) : le cosinus n'a pas de sens
    model = (getattr(settings, "ollama_embedding_model", "") or "").split(":")[0]
    return DEFAULT_THRESHOLDS.get(model, 0.0)


def best_similarity(search, dossier_id: str, queries: list[str]) -> float | None:
    """Meilleur cosinus entre une requête de la section et un passage du dossier (None si rien)."""
    texts = [q for q in queries if q.strip()]
    if not texts:
        return None
    retriever = search.retriever
    best: float | None = None
    for vec in retriever.provider.embed(texts):
        hits = retriever.repo.vector_search(dossier_id, vec, 1)
        if hits and (best is None or hits[0][1] > best):
            best = hits[0][1]
    return best


def below_threshold(search, dossier_id: str, queries: list[str], threshold: float) -> tuple[bool, float | None]:
    """(refuser ?, score). Désactivée si ``threshold`` <= 0."""
    if threshold <= 0:
        return False, None
    score = best_similarity(search, dossier_id, queries)
    return (score is None or score < threshold), score
