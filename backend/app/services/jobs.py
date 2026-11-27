"""Tâches longues suivies en direct : étape en cours, avancement, temps écoulé et restant, arrêt, historique.

Une tâche tourne dans un fil à part ; le code métier signale son avancement via `current()` (un suivi
« muet » hors tâche, donc rien ne change pour les appels directs et les tests). L'arrêt est vérifié avant
chaque appel au modèle : le modèle termine la réponse en cours, puis la tâche s'arrête proprement.
Le registre est en mémoire : un redémarrage du serveur efface l'historique des tâches (pas les résultats).
"""

from __future__ import annotations

import contextvars
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

MAX_STEPS = 400
KEEP_FINISHED = 50


class JobCancelled(Exception):
    """Levée dans le fil de la tâche quand l'utilisateur a demandé l'arrêt."""


@dataclass
class Job:
    id: str
    kind: str
    dossier_id: str
    label: str
    status: str = "running"  # running | done | failed | cancelled
    started: float = field(default_factory=time.time)
    ended: float | None = None
    done_units: int = 0
    total_units: int | None = None
    unit: str = ""
    current: str = ""
    steps: list[dict] = field(default_factory=list)
    result: dict | None = None
    error: str | None = None
    cancel_requested: bool = False
    phase_started: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ---- appelé par le code métier -------------------------------------------------------------
    def step(self, text: str) -> None:
        with self._lock:
            self.current = text
            self.steps.append({"t": round(time.time() - self.started, 1), "text": text})
            del self.steps[:-MAX_STEPS]

    def total(self, n: int, unit: str = "") -> None:
        with self._lock:
            self.total_units = max(n, 0)
            if unit:
                self.unit = unit

    def advance(self, n: int = 1) -> None:
        with self._lock:
            self.done_units += n

    def phase(self, n: int, unit: str = "") -> None:
        """Nouvelle phase : l'avancement repart de zéro (le temps restant aussi)."""
        with self._lock:
            self.done_units, self.total_units, self.unit = 0, max(n, 0), unit or self.unit
            self.phase_started = time.time()

    def check(self) -> None:
        if self.cancel_requested:
            raise JobCancelled

    # ---- lecture -------------------------------------------------------------------------------
    def view(self, with_steps: bool = True) -> dict:
        with self._lock:
            now = self.ended or time.time()
            elapsed = now - self.started
            remaining = None
            if self.status == "running" and self.total_units and self.done_units:
                spent = now - (self.phase_started or self.started)
                remaining = spent / self.done_units * max(self.total_units - self.done_units, 0)
            out = {"id": self.id, "kind": self.kind, "dossier_id": self.dossier_id, "label": self.label,
                   "status": self.status, "current": self.current, "elapsed_s": round(elapsed, 1),
                   "remaining_s": round(remaining, 1) if remaining is not None else None,
                   "done": self.done_units, "total": self.total_units, "unit": self.unit,
                   "cancel_requested": self.cancel_requested, "result": self.result, "error": self.error}
            if with_steps:
                out["steps"] = list(self.steps)
            return out


class _Silent:
    """Suivi muet hors d'une tâche."""

    def step(self, text: str) -> None: ...
    def total(self, n: int, unit: str = "") -> None: ...
    def advance(self, n: int = 1) -> None: ...
    def phase(self, n: int, unit: str = "") -> None: ...
    def check(self) -> None: ...


_SILENT = _Silent()
_current: contextvars.ContextVar = contextvars.ContextVar("cadrage_job", default=_SILENT)
_jobs: dict[str, Job] = {}
_registry_lock = threading.Lock()


def current():
    return _current.get()


def start(kind: str, dossier_id: str, label: str, fn: Callable[[], dict]) -> Job:
    job = Job(id="job_" + uuid.uuid4().hex[:12], kind=kind, dossier_id=dossier_id, label=label)
    with _registry_lock:
        _jobs[job.id] = job
        finished = [j for j in _jobs.values() if j.status != "running"]
        for old in sorted(finished, key=lambda j: j.started)[:-KEEP_FINISHED]:
            _jobs.pop(old.id, None)

    def run() -> None:
        _current.set(job)
        job.step("Démarrage")
        try:
            result = fn()
            job.result = result if isinstance(result, dict) else {"value": result}
            job.status = "done"
            job.step((job.result or {}).get("summary") or "Terminé")
        except JobCancelled:
            job.status = "cancelled"
            job.step("Arrêté à la demande de l'utilisateur")
        except Exception as exc:  # noqa: BLE001 — l'erreur est montrée à l'utilisateur, pas avalée
            job.status = "failed"
            job.error = getattr(exc, "message", None) or str(exc) or exc.__class__.__name__
            job.step(f"Échec : {job.error}")
        finally:
            job.ended = time.time()

    threading.Thread(target=run, name=job.id, daemon=True).start()
    return job


def get(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def running(dossier_id: str | None = None) -> list[Job]:
    return [j for j in list(_jobs.values())
            if j.status == "running" and (dossier_id is None or j.dossier_id == dossier_id)]


def recent(dossier_id: str) -> list[Job]:
    return sorted((j for j in list(_jobs.values()) if j.dossier_id == dossier_id),
                  key=lambda j: j.started, reverse=True)


def cancel(job_id: str) -> Job | None:
    job = _jobs.get(job_id)
    if job and job.status == "running":
        job.cancel_requested = True
        job.step("Arrêt demandé : la réponse en cours du modèle se termine, puis la tâche s'arrête")
    return job
