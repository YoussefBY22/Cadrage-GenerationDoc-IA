"""Fusion de classements par Reciprocal Rank Fusion."""


def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """score(d) = Σ 1 / (k + rang) ; rangs à partir de 1. Égalités : première apparition."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    order = {item: i for i, item in enumerate(scores)}
    return sorted(scores.items(), key=lambda x: (-x[1], order[x[0]]))
