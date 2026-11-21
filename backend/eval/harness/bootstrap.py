"""Intervalles de confiance par bootstrap sur les sections (graine fixe : résultat reproductible)."""

import random
import statistics


def bootstrap_ci(values: list[float], n: int = 1000, seed: int = 0,
                 alpha: float = 0.05) -> tuple[float, float]:
    """IC (1-alpha) de la moyenne, par rééchantillonnage avec remise."""
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    m = len(values)
    means = sorted(statistics.fmean(values[rng.randrange(m)] for _ in range(m)) for _ in range(n))
    return means[int(n * alpha / 2)], means[min(n - 1, int(n * (1 - alpha / 2)))]


def paired_diff_ci(a: list[float], b: list[float], n: int = 1000, seed: int = 0,
                   alpha: float = 0.05) -> tuple[float, float]:
    """IC de moyenne(a - b) sur des sections appariées (même ordre dans les deux listes)."""
    if len(a) != len(b):
        raise ValueError("les deux séries doivent porter sur les mêmes sections")
    return bootstrap_ci([x - y for x, y in zip(a, b, strict=True)], n, seed, alpha)
