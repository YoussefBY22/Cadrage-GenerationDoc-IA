"""Export d'une LoRA vers Ollama : fusion dans la base -> GGUF f16 -> quantification Q4_K_M -> Modelfile.

Ollama 0.40 refuse les adaptateurs (« LoRA adapters are no longer supported ») : on fusionne donc la LoRA
dans le modèle, puis llama.cpp convertit le tout. Le gabarit et les paramètres sont ceux de qwen3:4b, figés
dans `training/ollama/qwen3-4b.Modelfile` (et revérifiés contre Ollama quand il est là).

Pour une comparaison honnête, la base passe par la MÊME chaîne (`adapter_dir=None`) : même conversion, même
quantification, même Modelfile. Chaque GGUF reçoit son SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

GGUF_MAGIC = b"GGUF"
QUANT = "Q4_K_M"
MODELFILE = Path(__file__).parent / "ollama" / "qwen3-4b.Modelfile"
LICENCE_BASE = "Apache-2.0 (Qwen3-4B)"
OLLAMA = "http://127.0.0.1:11434"


class ExportError(RuntimeError):
    pass


def template_body(modelfile: str) -> str:
    """Gabarit + paramètres d'un Modelfile, sans FROM, commentaires ni licence."""
    kept = []
    for line in modelfile.replace("\r\n", "\n").splitlines():
        if line.startswith("LICENSE"):
            break  # texte de licence multi-lignes, toujours en fin de fichier
        if line.startswith(("FROM ", "# ")):
            continue
        kept.append(line)
    return "\n".join(kept).strip() + "\n"


def same_template(a: str, b: str) -> bool:
    """Même gabarit et mêmes paramètres ; l'ordre des lignes PARAMETER (qu'Ollama réordonne) ne compte pas."""
    def split(modelfile: str) -> tuple[list[str], list[str]]:
        lines = template_body(modelfile).splitlines()
        params = sorted(x for x in lines if x.startswith("PARAMETER "))
        return [x for x in lines if not x.startswith("PARAMETER ")], params
    return split(a) == split(b)


def modelfile_text(base_modelfile: str, gguf_name: str, licence: str = LICENCE_BASE) -> str:
    """Modelfile du modèle de base (gabarit, paramètres), avec FROM vers le GGUF fusionné."""
    return f'FROM ./{gguf_name}\n{template_body(base_modelfile).strip()}\nLICENSE "{licence}"\n'


def base_modelfile_text() -> str:
    return MODELFILE.read_text(encoding="utf-8")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify_export(out_dir: Path) -> None:
    """Lève ExportError si le GGUF, son empreinte ou le Modelfile manquent ou sont invalides."""
    gguf = out_dir / "model.gguf"
    modelfile = out_dir / "Modelfile"
    if not gguf.is_file() or gguf.stat().st_size < len(GGUF_MAGIC):
        raise ExportError(f"GGUF absent ou vide : {gguf}")
    with gguf.open("rb") as f:
        if f.read(4) != GGUF_MAGIC:
            raise ExportError("fichier GGUF invalide (en-tête incorrect)")
    if not modelfile.is_file() or "FROM ./model.gguf" not in modelfile.read_text("utf-8"):
        raise ExportError("Modelfile absent ou sans ligne FROM vers le GGUF")
    sha = out_dir / "model.gguf.sha256"
    if not sha.is_file() or sha.read_text("utf-8").split()[0] != file_sha256(gguf):
        raise ExportError("empreinte SHA-256 absente ou différente du GGUF")


def _run(cmd: list[str], what: str, cwd: Path | None = None) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             check=False, cwd=cwd)
    except OSError as e:
        raise ExportError(f"{what} impossible : {e}") from e
    if res.returncode != 0:
        raise ExportError(f"{what} a échoué : {(res.stderr or res.stdout)[-700:]}")
    return res.stdout


def check_template(base_tag: str = "qwen3:4b") -> None:
    """Le gabarit figé dans le dépôt doit être celui que cet Ollama donne à `base_tag` (lecture seule)."""
    live = _run(["ollama", "show", "--modelfile", base_tag], "lecture du gabarit Ollama")
    if not same_template(live, base_modelfile_text()):
        raise ExportError(f"le gabarit de {base_tag} dans Ollama diffère de training/ollama/qwen3-4b.Modelfile")


def quantize_tool(llama: Path) -> Path:
    for rel in ("build/bin/llama-quantize", "build/bin/llama-quantize.exe", "build/bin/Release/llama-quantize.exe"):
        if (llama / rel).is_file():
            return llama / rel
    raise ExportError("llama-quantize n'est pas compilé : lance la cellule « Compiler llama.cpp »")


def build_quantize(llama: Path) -> Path:
    """Compile seulement llama-quantize (CPU, sans CUDA : quelques minutes)."""
    try:
        return quantize_tool(llama)
    except ExportError:
        pass
    _run(["cmake", "-S", str(llama), "-B", str(llama / "build"), "-DGGML_CUDA=OFF", "-DLLAMA_CURL=OFF",
          "-DCMAKE_BUILD_TYPE=Release"], "cmake llama.cpp")
    _run(["cmake", "--build", str(llama / "build"), "--target", "llama-quantize", "-j", str(os.cpu_count() or 2)],
         "compilation de llama-quantize")
    return quantize_tool(llama)


def _merge(adapter_dir: Path | None, base_model_dir: Path, merged: Path) -> Path:
    """Dossier safetensors à convertir (la base elle-même s'il n'y a pas d'adaptateur)."""
    if adapter_dir is None:
        return base_model_dir
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model = AutoModelForCausalLM.from_pretrained(base_model_dir, dtype=torch.float16, low_cpu_mem_usage=True)
    model = PeftModel.from_pretrained(model, adapter_dir).merge_and_unload()
    model.save_pretrained(merged, safe_serialization=True)
    AutoTokenizer.from_pretrained(base_model_dir).save_pretrained(merged)
    return merged


def export(adapter_dir: Path | None, out_dir: Path, base_tag: str = "qwen3:4b",
           simulate: bool = False, base_model_dir: Path | None = None,
           ollama_tag: str | None = None) -> Path:
    """Écrit `model.gguf` (Q4_K_M), `model.gguf.sha256`, `Modelfile` ; avec `ollama_tag`, les importe et les fait répondre."""
    out_dir.mkdir(parents=True, exist_ok=True)
    gguf = out_dir / "model.gguf"
    if simulate:
        gguf.write_bytes(GGUF_MAGIC + bytes([0]) + b"simulation")
    else:
        llama = os.environ.get("LLAMA_CPP_DIR")
        script = Path(llama or ".") / "convert_hf_to_gguf.py"
        if not llama or not script.is_file():
            raise ExportError("LLAMA_CPP_DIR doit pointer vers un dépôt llama.cpp local")
        if base_model_dir is None:
            raise ExportError("base_model_dir est requis pour fusionner la LoRA")
        quantize = quantize_tool(Path(llama))
        check_template(base_tag)
        merged = out_dir / "merged"
        f16 = out_dir / "model-f16.gguf"
        try:
            source = _merge(adapter_dir, base_model_dir, merged)
            _run([sys.executable, str(script), str(source), "--outfile", str(f16), "--outtype", "f16"],
                 "conversion GGUF f16")
            shutil.rmtree(merged, ignore_errors=True)
            _run([str(quantize), str(f16), str(gguf), QUANT], f"quantification {QUANT}")
        finally:
            shutil.rmtree(merged, ignore_errors=True)
            f16.unlink(missing_ok=True)
    # LF obligatoire : en CRLF, le gabarit change les jetons envoyés au modèle (constaté le 22/11).
    (out_dir / "Modelfile").write_text(modelfile_text(base_modelfile_text(), "model.gguf"),
                                       encoding="utf-8", newline="\n")
    (out_dir / "model.gguf.sha256").write_text(f"{file_sha256(gguf)}  model.gguf\n", encoding="utf-8", newline="\n")
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
    ap.add_argument("--base-tag", default="qwen3:4b")
    ap.add_argument("--base-model-dir", type=Path)
    ap.add_argument("--ollama-tag")
    ap.add_argument("--simulate", action="store_true")
    a = ap.parse_args()
    export(a.adapter, a.out, a.base_tag, a.simulate, a.base_model_dir, a.ollama_tag)
    print(f"Export vérifié dans {a.out}")


if __name__ == "__main__":
    main()
