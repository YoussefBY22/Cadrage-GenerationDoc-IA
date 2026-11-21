"""Indicateurs (07 §5) : fonctions pures sur des lignes (dictionnaires).

Les mêmes chiffres doivent sortir des vues SQL (test de cohérence vue ↔ Python).
Convention : un rapport sans dénominateur renvoie `None` (le NULL de SQL).
"""

import math
import statistics
from collections.abc import Iterable, Mapping
from typing import Any

Row = Mapping[str, Any]


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def tpv(generations: Iterable[Row]) -> float | None:
    """Taux de phrases vérifiées : Σ verified / Σ total (générations `ok`)."""
    ok = [g for g in generations if g["status"] == "ok"]
    return _ratio(sum(g["sentences_verified"] for g in ok), sum(g["sentences_total"] for g in ok))


def citations_valid_rate(generations: Iterable[Row]) -> float | None:
    gens = list(generations)
    return _ratio(sum(g["citations_valid"] for g in gens), sum(g["citations_total"] for g in gens))


def number_fidelity(generations: Iterable[Row]) -> float:
    """Σ numbers_found / Σ numbers_cited ; 1 si aucun chiffre cité."""
    gens = list(generations)
    cited = sum(g["numbers_cited"] for g in gens)
    return 1.0 if cited == 0 else sum(g["numbers_found"] for g in gens) / cited


def refusal_rate(generations: Iterable[Row]) -> float | None:
    gens = list(generations)
    return _ratio(sum(1 for g in gens if g["status"] == "refused"), len(gens))


def invalid_rate(generations: Iterable[Row]) -> float | None:
    gens = list(generations)
    return _ratio(sum(1 for g in gens if g["status"] == "invalid"), len(gens))


def unchanged_rate(outcomes: Iterable[Row]) -> float | None:
    """Acceptation sans modification : outcomes `unchanged` / outcomes."""
    rows = list(outcomes)
    return _ratio(sum(1 for o in rows if o["unchanged"]), len(rows))


def mean_edit_ratio(outcomes: Iterable[Row]) -> float | None:
    rows = list(outcomes)
    return _ratio(sum(o["edit_ratio"] for o in rows), len(rows))


def minutes_saved(outcomes: Iterable[Row]) -> float:
    """Temps gagné estimé (minutes) = Σ minutes_saved_est (= baseline × (1 − edit_ratio))."""
    return float(sum(o["minutes_saved_est"] for o in outcomes))


def percentile(values: Iterable[float], p: float) -> float | None:
    """Percentile inclusif à interpolation linéaire (équivalent de PERCENTILEX.INC), p dans [0, 1]."""
    xs = sorted(values)
    if not xs:
        return None
    pos = (len(xs) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def latency_percentile(calls: Iterable[Row], p: float) -> float | None:
    return percentile([c["latency_ms"] for c in calls if c["latency_ms"] is not None], p)


def throughput_tokens_per_s(calls: Iterable[Row]) -> float | None:
    """Σ tokens_out / Σ latence en secondes."""
    rows = [c for c in calls if c["latency_ms"] is not None and c["tokens_out"] is not None]
    return _ratio(sum(c["tokens_out"] for c in rows), sum(c["latency_ms"] for c in rows) / 1000.0)


def review_delay_hours(reviews: Iterable[Row]) -> float | None:
    """Médiane du délai (h) entre la 1ʳᵉ soumission et l'approbation, par livrable."""
    delays = [float(r["hours_since_submission"]) for r in reviews
              if r["to_state"] == "approved"]
    return statistics.median(delays) if delays else None


def review_rejection_rate(reviews: Iterable[Row]) -> float | None:
    """Transitions → rejected / soumissions (transitions → in_review)."""
    rows = list(reviews)
    return _ratio(sum(1 for r in rows if r["to_state"] == "rejected"),
                  sum(1 for r in rows if r["to_state"] == "in_review"))


def injection_alerts(documents: Iterable[Row]) -> int:
    return int(sum(d["injection_alert_count"] for d in documents))
