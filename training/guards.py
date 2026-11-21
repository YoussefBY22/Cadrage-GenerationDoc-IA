"""Garde-fous d'entraînement : perte invalide, disque presque plein, GPU trop chaud, arrêt demandé.

Chaque contrôle renvoie `None` (tout va bien) ou une raison d'arrêt ; l'appelant sauvegarde un
point de reprise puis s'arrête proprement. Aucune dépendance lourde.
"""

from __future__ import annotations

import math
import shutil
import signal
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GuardConfig:
    min_free_gb: float = 5.0
    max_gpu_temp: float = 83.0
    loss_explosion_factor: float = 3.0


def check_loss(loss: float, initial_loss: float | None, factor: float = 3.0) -> str | None:
    """NaN/inf, ou perte > `factor` × perte initiale."""
    if loss is None or math.isnan(loss) or math.isinf(loss):
        return f"perte invalide ({loss})"
    if initial_loss is not None and initial_loss > 0 and loss > factor * initial_loss:
        return f"perte en explosion ({loss:.3f} > {factor} x {initial_loss:.3f})"
    return None


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def check_disk(path: Path, min_free_gb: float,
               free_fn: Callable[[Path], float] = free_gb) -> str | None:
    free = free_fn(path)
    if free < min_free_gb:
        return f"disque presque plein ({free:.1f} Go libres < {min_free_gb} Go)"
    return None


def gpu_temperature() -> float | None:
    """Température max des GPU via nvidia-smi ; None si l'outil est absent ou illisible."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=False)
        temps = [float(x) for x in res.stdout.split() if x.strip()]
        return max(temps) if temps else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def check_temperature(max_temp: float,
                      temp_fn: Callable[[], float | None] = gpu_temperature) -> str | None:
    t = temp_fn()
    if t is not None and t > max_temp:
        return f"GPU trop chaud ({t:.0f} °C > {max_temp:.0f} °C)"
    return None


class StopFlag:
    """Drapeau d'arrêt propre, levé par Ctrl+C / SIGTERM (ou à la main dans les tests)."""

    def __init__(self) -> None:
        self.requested = False

    def request(self, *_args) -> None:
        self.requested = True

    def install(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self.request)
            except ValueError:  # hors du fil principal
                pass


def check_all(loss: float, initial_loss: float | None, run_dir: Path, cfg: GuardConfig,
              *, free_fn: Callable[[Path], float] = free_gb,
              temp_fn: Callable[[], float | None] = gpu_temperature,
              stop: StopFlag | None = None) -> str | None:
    """Premier garde-fou déclenché, ou None."""
    if stop is not None and stop.requested:
        return "arrêt demandé par l'utilisateur"
    return (check_loss(loss, initial_loss, cfg.loss_explosion_factor)
            or check_disk(run_dir, cfg.min_free_gb, free_fn)
            or check_temperature(cfg.max_gpu_temp, temp_fn))
