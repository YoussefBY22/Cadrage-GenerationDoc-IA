"""Calcul déterministe et explicable de la priorité des initiatives (FR-09)."""

import math

from app.domain.roadmap import Criterion, Initiative, ScoredInitiative

DEFAULT_CRITERIA: list[Criterion] = [
    Criterion(key="impact", label="Impact", weight=0.35),
    Criterion(key="urgence", label="Urgence", weight=0.25),
    Criterion(key="faisabilite", label="Faisabilité", weight=0.20),
    Criterion(key="cout", label="Coût", weight=0.10, higher_is_better=False),
    Criterion(key="risque", label="Risque", weight=0.10, higher_is_better=False),
]


def _normalized_weights(criteria: list[Criterion]) -> list[float]:
    total = sum(c.weight for c in criteria)
    if total <= 0:
        raise ValueError("La somme des poids des critères doit être positive")
    return [c.weight / total for c in criteria]


def _contributions(
    initiative: Initiative, criteria: list[Criterion], warnings: list[str] | None = None
) -> list[tuple[Criterion, float, int, float]]:
    """(critère, poids renormalisé, valeur brute, valeur normalisée/inversée)."""
    by_key = {s.key: s.value for s in initiative.scores}
    out = []
    for crit, w in zip(criteria, _normalized_weights(criteria), strict=True):
        raw = by_key.get(crit.key)
        if raw is None:
            raw = 1
            if warnings is not None:
                warnings.append(
                    f"Initiative {initiative.id} : critère « {crit.key} » sans score, valeur 1 retenue"
                )
        norm = (raw - 1) / 4
        if not crit.higher_is_better:
            norm = 1 - norm
        out.append((crit, w, raw, norm))
    return out


def score_with_warnings(
    initiatives: list[Initiative], criteria: list[Criterion], waves: int = 3
) -> tuple[list[ScoredInitiative], list[str]]:
    """Comme `score`, mais renvoie aussi les avertissements (critères manquants)."""
    if waves < 1:
        raise ValueError("waves doit être >= 1")
    warnings: list[str] = []
    values = {}
    for ini in initiatives:
        contribs = _contributions(ini, criteria, warnings)
        values[ini.id] = round(sum(w * n for _, w, _, n in contribs), 4)
    order = sorted(initiatives, key=lambda i: (-values[i.id], i.id))
    n = len(order)
    wave = {ini.id: math.ceil((r + 1) * waves / n) for r, ini in enumerate(order)}
    # Une initiative n'est jamais dans une vague antérieure à ses prérequis.
    # Itération à point fixe, bornée (les cycles saturent à `waves`).
    deps = {i.id: [d for d in i.depends_on if d in wave] for i in initiatives}
    for _ in range(n + 1):
        changed = False
        for iid, ds in deps.items():
            need = min(max((wave[d] for d in ds), default=1), waves)
            if wave[iid] < need:
                wave[iid] = need
                changed = True
        if not changed:
            break
    items = [
        ScoredInitiative(initiative=ini, score=values[ini.id], rank=r + 1, wave=wave[ini.id])
        for r, ini in enumerate(order)
    ]
    return items, warnings


def score(
    initiatives: list[Initiative], criteria: list[Criterion], waves: int = 3
) -> list[ScoredInitiative]:
    """Priorise : valeurs normalisées, pondérées, arrondies ; rang, vagues."""
    return score_with_warnings(initiatives, criteria, waves)[0]


def _fr(x: float, nd: int) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def explain(item: ScoredInitiative, criteria: list[Criterion] | None = None) -> str:
    """Texte « score = 0,35×… » détaillant le calcul pour l'interface."""
    criteria = DEFAULT_CRITERIA if criteria is None else criteria
    parts = []
    for crit, w, raw, norm in _contributions(item.initiative, criteria):
        inv = " inversé" if not crit.higher_is_better else ""
        parts.append(f"{_fr(w, 2)}×{_fr(norm, 2)} ({crit.label} {raw}/5{inv})")
    return (
        f"score = {' + '.join(parts)} = {_fr(item.score, 4)} "
        f"(rang {item.rank}, vague {item.wave})"
    )
