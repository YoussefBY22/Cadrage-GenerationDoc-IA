"""Persistance du registre : un fichier JSON local (ignoré par Git), écrit atomiquement, sans migration."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

VERSION = 1
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _empty() -> dict:
    return {"version": VERSION, "active": None, "history": [], "tests": {}}


class RegistryStore:
    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path)

    def load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return _empty()
        except (OSError, ValueError):
            # fichier abîmé : on le garde de côté plutôt que de le perdre, et on repart d'un état vide
            try:
                self.path.replace(self.path.with_suffix(".corrupt"))
            except OSError:
                pass
            return _empty()
        if not isinstance(data, dict):
            return _empty()
        return {**_empty(), **data}

    def save(self, data: dict) -> None:
        """Écriture atomique : fichier temporaire dans le même dossier, puis remplacement."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # --- opérations (verrou : un seul écrivain à la fois dans ce processus) -----------------------
    def active(self) -> str | None:
        return self.load().get("active")

    def record_test(self, name: str, result: dict) -> None:
        with _lock:
            data = self.load()
            data["tests"][name] = result
            self.save(data)

    def last_test(self, name: str) -> dict | None:
        return self.load()["tests"].get(name)

    def set_active(self, name: str, *, by: str | None, action: str, base: str | None = None) -> dict:
        """Active `name` ; la première activation consigne d'abord le modèle de la configuration (retour possible)."""
        with _lock:
            data = self.load()
            if not data["history"] and base and base != name:
                data["history"].append({"at": _now(), "by": None, "action": "initial", "model": base})
            previous = data["active"] or base
            entry = {"at": _now(), "by": by, "action": action, "model": name, "previous": previous}
            data["history"].append(entry)
            data["active"] = name
            self.save(data)
            return entry

    def previous_model(self, current: str | None) -> str | None:
        for entry in reversed(self.load()["history"]):
            if entry["model"] != current:
                return entry["model"]
        return None


def active_model_resolver(settings) -> Callable[[], str | None]:
    """Modèle actif relu à chaque appel (mise en cache par date de modification : un `stat` seulement)."""
    store = RegistryStore(settings.models_registry_path)
    cache: dict = {"stamp": None, "model": None}

    def resolve() -> str | None:
        try:
            stamp = store.path.stat().st_mtime_ns
        except OSError:
            return None
        if stamp != cache["stamp"]:
            cache["model"], cache["stamp"] = store.active(), stamp
        return cache["model"]

    return resolve
