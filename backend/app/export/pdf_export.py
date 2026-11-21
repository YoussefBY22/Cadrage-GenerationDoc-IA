"""Export PDF : conversion du DOCX par LibreOffice (soffice) en mode sans interface."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.config import get_settings

from .common import ExportData, ExportUnavailable
from .docx_export import render_docx

TIMEOUT_SECONDS = 60


def soffice_binary() -> str | None:
    return shutil.which(get_settings().soffice_path)


def render_pdf(data: ExportData, path: Path) -> None:
    binary = soffice_binary()
    if binary is None:
        raise ExportUnavailable("LibreOffice (soffice) est absent : export PDF indisponible")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "livrable.docx"
        render_docx(data, src)
        try:
            subprocess.run(
                [binary, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(src)],
                check=True, timeout=TIMEOUT_SECONDS, capture_output=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            raise ExportUnavailable(f"conversion PDF échouée : {type(exc).__name__}") from exc
        shutil.move(str(Path(tmp) / "livrable.pdf"), str(path))
