"""Export d'un adaptateur LoRA vers GGUF + Modelfile Ollama (ADAPTER), avec vérification.

L'export est testé **avant** le long entraînement (essai sur 1 %). En simulation, un faux GGUF est
écrit : la même vérification (`verify_export`) s'applique donc au vrai comme au faux.
Réel : nécessite llama.cpp (variable LLAMA_CPP_DIR) ; non exécuté cette nuit.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

GGUF_MAGIC = b"GGUF"


class ExportError(RuntimeError):
    pass


def modelfile_text(base_tag: str, adapter_file: str) -> str:
    return f"FROM {base_tag}\nADAPTER {adapter_file}\nPARAMETER temperature 0.2\n"


def verify_export(out_dir: Path) -> None:
    """Lève ExportError si l'adaptateur GGUF ou le Modelfile manquent ou sont invalides."""
    gguf = out_dir / "adapter.gguf"
    modelfile = out_dir / "Modelfile"
    if not gguf.is_file() or gguf.stat().st_size < len(GGUF_MAGIC):
        raise ExportError(f"adaptateur GGUF absent ou vide : {gguf}")
    if gguf.read_bytes()[:4] != GGUF_MAGIC:
        raise ExportError("fichier GGUF invalide (en-tête incorrect)")
    if not modelfile.is_file() or "ADAPTER" not in modelfile.read_text("utf-8"):
        raise ExportError("Modelfile absent ou sans ligne ADAPTER")


def export(adapter_dir: Path, out_dir: Path, base_tag: str = "qwen3:1.7b",
           simulate: bool = False, base_model_dir: Path | None = None) -> Path:
    """Convertit l'adaptateur en GGUF et écrit le Modelfile ; retourne le dossier de sortie."""
    out_dir.mkdir(parents=True, exist_ok=True)
    gguf = out_dir / "adapter.gguf"
    if simulate:
        gguf.write_bytes(GGUF_MAGIC + b"\x00simulation")
    else:
        llama = os.environ.get("LLAMA_CPP_DIR")
        if not llama or not (Path(llama) / "convert_lora_to_gguf.py").is_file():
            raise ExportError("LLAMA_CPP_DIR doit pointer vers un dépôt llama.cpp local")
        if base_model_dir is None:
            raise ExportError("base_model_dir est requis pour convertir l'adaptateur")
        cmd = [sys.executable, str(Path(llama) / "convert_lora_to_gguf.py"), str(adapter_dir),
               "--base", str(base_model_dir), "--outfile", str(gguf), "--outtype", "f16"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise ExportError(f"conversion GGUF échouée : {res.stderr[-500:]}")
    (out_dir / "Modelfile").write_text(modelfile_text(base_tag, "adapter.gguf"), encoding="utf-8")
    verify_export(out_dir)
    return out_dir


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adapter", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--base-tag", default="qwen3:1.7b")
    ap.add_argument("--base-model-dir", type=Path)
    ap.add_argument("--simulate", action="store_true")
    a = ap.parse_args()
    export(a.adapter, a.out, a.base_tag, a.simulate, a.base_model_dir)
    print(f"Export vérifié dans {a.out} ; ensuite : ollama create cadrage-lora -f {a.out}/Modelfile")


if __name__ == "__main__":
    main()
