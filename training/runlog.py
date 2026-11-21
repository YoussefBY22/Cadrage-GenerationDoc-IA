"""Journal d'un entraînement : training/runs/<id>/run.json (écriture atomique)."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

LIBS = ["torch", "transformers", "peft", "trl", "bitsandbytes", "accelerate", "datasets"]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def library_versions() -> dict[str, str | None]:
    """Versions installées (sans importer les bibliothèques) ; None si absente."""
    out: dict[str, str | None] = {"python": sys.version.split()[0]}
    for lib in LIBS:
        try:
            out[lib] = metadata.version(lib)
        except metadata.PackageNotFoundError:
            out[lib] = None
    return out


def hardware_info() -> dict:
    info: dict = {"platform": platform.platform(), "cpu_count": os.cpu_count(), "gpu": None}
    if shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                 "--format=csv,noheader"], capture_output=True, text=True, timeout=10, check=False)
            info["gpu"] = res.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            pass
    return info


class RunLog:
    """Contenu de run.json : versions, graine, paramètres, empreintes, durée, métriques."""

    def __init__(self, run_dir: Path, run_id: str, seed: int, params: dict,
                 data_files: dict[str, Path], simulate: bool):
        self.path = run_dir / "run.json"
        run_dir.mkdir(parents=True, exist_ok=True)
        previous = json.loads(self.path.read_text("utf-8")) if self.path.exists() else None
        self.data = {
            "run_id": run_id,
            "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "simulate": simulate,
            "seed": seed,
            "params": params,
            "versions": library_versions(),
            "hardware": hardware_info(),
            "data_hashes": {k: file_sha256(p) for k, p in data_files.items() if p.exists()},
            "status": "running",
            "stop_reason": None,
            "phases": [],
            "metrics": [],
            "duration_seconds": 0.0,
            "resumed_from_step": None,
            "attempts": (previous["attempts"] + 1) if previous else 1,
        }
        self.save()

    def phase(self, name: str, **info) -> None:
        self.data["phases"].append({"name": name, **info})
        self.save()

    def metric(self, step: int, **values: float) -> None:
        self.data["metrics"].append({"step": step, **values})

    def finish(self, status: str, duration_seconds: float, stop_reason: str | None = None) -> None:
        self.data.update(status=status, stop_reason=stop_reason,
                         duration_seconds=round(duration_seconds, 2))
        self.save()

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
