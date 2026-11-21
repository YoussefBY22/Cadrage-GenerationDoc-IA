"""Métriques de 08 §6 : fonctions pures, sans dépendance au stockage ni au modèle."""

import math
import re
import statistics


def norm(text: str) -> str:
    """Minuscules, espaces (dont insécables) réduits : comparaison de marqueurs."""
    return re.sub(r"\s+", " ", text.replace(" ", " ").replace(" ", " ")).strip().lower()


def first_hit_rank(passages: list[str], markers: list[str]) -> int | None:
    """Rang (1-based) du premier passage contenant tous les marqueurs ; None si absent."""
    ms = [norm(m) for m in markers]
    for i, p in enumerate(passages, 1):
        t = norm(p)
        if all(m in t for m in ms):
            return i
    return None


def recall_at_k(ranks: list[int | None], k: int) -> float:
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks) if ranks else 0.0


def mrr(ranks: list[int | None]) -> float:
    return sum(1 / r for r in ranks if r) / len(ranks) if ranks else 0.0


def citation_validity(sentences: list[tuple[int, bool]]) -> float:
    """sentences : (nombre de citations, phrase avec problème bloquant). Citations valides / citations."""
    total = sum(n for n, _ in sentences)
    return sum(n for n, bad in sentences if not bad) / total if total else 1.0


def number_fidelity(cited: int, found: int) -> float:
    return found / cited if cited else 1.0


def structure_validity(first_try_ok: list[bool]) -> float:
    return sum(first_try_ok) / len(first_try_ok) if first_try_ok else 1.0


def finding_coverage(gold_markers: list[list[str]], produced_evidence: list[str]) -> float:
    """Part des constats or dont au moins un marqueur de preuve figure dans les preuves citées."""
    if not gold_markers:
        return 1.0
    ev = norm(" ".join(produced_evidence))
    return sum(1 for ms in gold_markers if any(norm(m) in ev for m in ms)) / len(gold_markers)


def dependency_recall(gold: set[tuple[str, str]], produced: set[tuple[str, str]]) -> float:
    return len(gold & produced) / len(gold) if gold else 1.0


def refusal_rates(expected_refusal: list[bool], refused: list[bool]) -> tuple[float, float]:
    """(refus manqués sur sections sans preuve, faux refus sur sections avec preuves)."""
    no_ev = [r for e, r in zip(expected_refusal, refused, strict=True) if e]
    ev = [r for e, r in zip(expected_refusal, refused, strict=True) if not e]
    missed = sum(1 for r in no_ev if not r) / len(no_ev) if no_ev else 0.0
    false = sum(1 for r in ev if r) / len(ev) if ev else 0.0
    return missed, false


def attack_rate(succeeded: list[bool]) -> float:
    return sum(succeeded) / len(succeeded) if succeeded else 0.0


def percentile(values: list[float], p: float) -> float:
    """Percentile par interpolation linéaire (p dans 0..100)."""
    if not values:
        return 0.0
    v = sorted(values)
    pos = (len(v) - 1) * p / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def mean_sd(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    return statistics.fmean(values), (statistics.stdev(values) if len(values) > 1 else 0.0)
