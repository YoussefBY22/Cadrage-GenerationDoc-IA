"""Export d'une LoRA vers Ollama : fusion dans la base -> GGUF complet -> Modelfile -> essai réel.

Ollama 0.40 refuse les adaptateurs (« LoRA adapters are no longer supported ») : on fusionne donc
la LoRA dans le modèle, puis llama.cpp convertit le tout (q8_0, sans compilation). L'export est
testé **avant** tout entraînement long. En simulation, un faux GGUF passe la même vérification.

Pour une comparaison honnête, la base doit passer par la même chaîne (`adapter_dir=None`).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

GGUF_MAGIC = b"GGUF"
OLLAMA = "http://127.0.0.1:11434"


class ExportError(RuntimeError):
    pass


def modelfile_text(base_modelfile: str, gguf_name: str) -> str:
    """Modelfile du modèle de base (gabarit, paramètres), avec FROM vers le GGUF fusionné."""
    kept = []
    for line in base_modelfile.splitlines():
        if line.startswith("LICENSE"):
            break  # texte de licence multi-lignes, toujours en fin de fichier
        if line.startswith(("FROM ", "# ")):
            continue
        kept.append(line)
    body = "\n".join(kept).strip()
    return f'FROM ./{gguf_name}\n{body}\nLICENSE "Apache-2.0 (Qwen3-1.7B)"\n'


def verify_export(out_dir: Path) -> None:
    """Lève ExportError si le GGUF ou le Modelfile manquent ou sont invalides."""
    gguf = out_dir / "model.gguf"
    modelfile = out_dir / "Modelfile"
    if not gguf.is_file() or gguf.stat().st_size < len(GGUF_MAGIC):
        raise ExportError(f"GGUF absent ou vide : {gguf}")
    with gguf.open("rb") as f:
        if f.read(4) != GGUF_MAGIC:
            raise ExportError("fichier GGUF invalide (en-tête incorrect)")
    if not modelfile.is_file() or "FROM ./model.gguf" not in modelfile.read_text("utf-8"):
        raise ExportError("Modelfile absent ou sans ligne FROM vers le GGUF")


def _run(cmd: list[str], what: str, cwd: Path | None = None) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             check=False, cwd=cwd)
    except OSError as e:
        raise ExportError(f"{what} impossible : {e}") from e
    if res.returncode != 0:
        raise ExportError(f"{what} a échoué : {(res.stderr or res.stdout)[-700:]}")
    return res.stdout


def _merge(adapter_dir: Path | None, base_model_dir: Path, merged: Path) -> Path:
    """Dossier safetensors à convertir (la base elle-même s'il n'y a pas d'adaptateur)."""
    if adapter_dir is None:
        return base_model_dir
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model = AutoModelForCausalLM.from_pretrained(base_model_dir, dtype=torch.float16)
    model = PeftModel.from_pretrained(model, adapter_dir).merge_and_unload()
    model.save_pretrained(merged, safe_serialization=True)
    AutoTokenizer.from_pretrained(base_model_dir).save_pretrained(merged)
    return merged


def export(adapter_dir: Path | None, out_dir: Path, base_tag: str = "qwen3:1.7b",
           simulate: bool = False, base_model_dir: Path | None = None,
           ollama_tag: str | None = None) -> Path:
    """Écrit `model.gguf` et `Modelfile` ; avec `ollama_tag`, les importe et les fait répondre."""
    out_dir.mkdir(parents=True, exist_ok=True)
    gguf = out_dir / "model.gguf"
    if simulate:
        gguf.write_bytes(GGUF_MAGIC + b"\x00simulation")
        base_modelfile = ""
    else:
        llama = os.environ.get("LLAMA_CPP_DIR")
        script = Path(llama or ".") / "convert_hf_to_gguf.py"
        if not llama or not script.is_file():
            raise ExportError("LLAMA_CPP_DIR doit pointer vers un dépôt llama.cpp local")
        if base_model_dir is None:
            raise ExportError("base_model_dir est requis pour fusionner la LoRA")
        base_modelfile = _run(["ollama", "show", "--modelfile", base_tag], "lecture du gabarit Ollama")
        merged = out_dir / "merged"
        try:
            source = _merge(adapter_dir, base_model_dir, merged)
            _run([sys.executable, str(script), str(source), "--outfile", str(gguf), "--outtype", "q8_0"],
                 "conversion GGUF")
        finally:
            shutil.rmtree(merged, ignore_errors=True)
    # LF obligatoire : en CRLF, le gabarit change les jetons envoyés au modèle (constaté le 22/11).
    (out_dir / "Modelfile").write_text(modelfile_text(base_modelfile, "model.gguf"),
                                       encoding="utf-8", newline="\n")
    verify_export(out_dir)
    if ollama_tag and not simulate:
        ollama_check(ollama_tag, out_dir / "Modelfile")
    return out_dir


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(f"{OLLAMA}{path}", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ExportError(f"Ollama {path} : {e.code} {e.read()[:300]!r}") from e
    except OSError as e:
        raise ExportError(f"Ollama ne répond pas : {e}") from e


def ollama_check(tag: str, modelfile: Path) -> str:
    """`ollama create` puis une vraie réponse : l'import marche réellement."""
    _run(["ollama", "create", tag, "-f", modelfile.name], "ollama create", cwd=modelfile.parent)
    out = post("/api/chat", {
        "model": tag, "stream": False, "think": False, "keep_alive": 0,
        "messages": [{"role": "user", "content": "Réponds par le mot : ok"}],
        "options": {"num_predict": 24}})
    if not out.get("eval_count"):
        raise ExportError("le modèle importé n'a produit aucun jeton")
    return out["message"]["content"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adapter", type=Path, help="absent : exporte la base seule")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--base-tag", default="qwen3:1.7b")
    ap.add_argument("--base-model-dir", type=Path)
    ap.add_argument("--ollama-tag")
    ap.add_argument("--simulate", action="store_true")
    a = ap.parse_args()
    export(a.adapter, a.out, a.base_tag, a.simulate, a.base_model_dir, a.ollama_tag)
    print(f"Export vérifié dans {a.out}")


if __name__ == "__main__":
    main()
