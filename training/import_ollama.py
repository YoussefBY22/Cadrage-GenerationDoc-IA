"""Côté PC : importer dans Ollama les deux GGUF fabriqués sur Colab (base et base + LoRA).

    python -m training.import_ollama --lora DOSSIER/cadrage-4b-lora --base DOSSIER/cadrage-4b-base [--sums SHA256SUMS.txt]

Pour chaque dossier (model.gguf + model.gguf.sha256) :
  1. l'empreinte SHA-256 du GGUF est recalculée et comparée à celle du fichier .sha256 (et à SHA256SUMS.txt) ;
  2. le gabarit de qwen3:4b dans CET Ollama est comparé à celui du dépôt ; refus s'ils diffèrent ;
  3. `ollama create cadrage-4b-base` / `cadrage-4b-lora`, avec le gabarit et les paramètres de qwen3:4b
     (training/ollama/qwen3-4b.Modelfile), puis l'empreinte du fichier importé est revérifiée dans Ollama ;
  4. une réponse de contrôle courte prouve que le modèle répond (c'est le SEUL calcul fait, sur ton GPU).

Rien n'est téléchargé, rien n'est fusionné ici : les GGUF viennent de Colab.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from training import export_gguf
from training.export_gguf import ExportError, file_sha256

TAGS = {"base": "cadrage-4b-base", "lora": "cadrage-4b-lora"}
BASE_TAG = "qwen3:4b"


def expected_sha(folder: Path, sums: Path | None = None) -> str:
    """Empreinte attendue du GGUF d'un dossier ; si `sums` est donné, il doit dire la même chose."""
    sha_file = folder / "model.gguf.sha256"
    if not sha_file.is_file():
        raise ExportError(f"{sha_file} manque : télécharge aussi le fichier .sha256")
    sha = sha_file.read_text("utf-8").split()[0].lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise ExportError(f"{sha_file} : empreinte illisible")
    if sums is not None:
        listed = {line.split()[1]: line.split()[0].lower() for line in sums.read_text("utf-8").splitlines() if line.strip()}
        key = f"{folder.name}/model.gguf"
        if listed.get(key) != sha:
            raise ExportError(f"{key} : l'empreinte diffère de celle de SHA256SUMS.txt")
    return sha


def check_files(folder: Path, sums: Path | None = None) -> str:
    gguf = folder / "model.gguf"
    if not gguf.is_file():
        raise ExportError(f"{gguf} introuvable")
    with gguf.open("rb") as f:
        if f.read(4) != export_gguf.GGUF_MAGIC:
            raise ExportError(f"{gguf} : ce n'est pas un fichier GGUF")
    want = expected_sha(folder, sums)
    got = file_sha256(gguf)
    if got != want:
        raise ExportError(f"{gguf} : SHA-256 différent ({got[:12]}… au lieu de {want[:12]}…) : téléchargement abîmé, recommence")
    return got


def import_one(kind: str, folder: Path, sums: Path | None = None, say=print) -> str:
    """Importe un dossier ; renvoie la réponse de contrôle."""
    tag = TAGS[kind]
    sha = check_files(folder, sums)
    say(f"[{tag}] empreinte vérifiée : {sha[:16]}…")
    export_gguf.check_template(BASE_TAG)
    say(f"[{tag}] gabarit de {BASE_TAG} identique à celui du dépôt")
    modelfile = folder / "Modelfile"
    modelfile.write_text(export_gguf.modelfile_text(export_gguf.base_modelfile_text(), "model.gguf"),
                         encoding="utf-8", newline="\n")
    export_gguf._run(["ollama", "create", tag, "-f", modelfile.name], "ollama create", cwd=folder)
    shown = export_gguf._run(["ollama", "show", "--modelfile", tag], "relecture du modèle importé")
    if f"sha256-{sha}" not in shown.replace("\\", "/").lower():
        raise ExportError(f"{tag} : le fichier importé par Ollama n'a pas l'empreinte du GGUF")
    if not export_gguf.same_template(shown, export_gguf.base_modelfile_text()):
        raise ExportError(f"{tag} : le gabarit importé n'est pas celui de {BASE_TAG}")
    say(f"[{tag}] importé, empreinte et gabarit relus dans Ollama")
    reply = _control(tag)
    say(f"[{tag}] réponse de contrôle : {reply!r}")
    return reply


def _control(tag: str) -> str:
    out = export_gguf.post("/api/chat", {
        "model": tag, "stream": False, "think": False, "keep_alive": 0,
        "messages": [{"role": "user", "content": "Réponds uniquement par le mot : ok"}],
        "options": {"num_predict": 24, "temperature": 0, "seed": 0}})
    if not out.get("eval_count"):
        raise ExportError(f"{tag} : le modèle n'a produit aucun jeton")
    return out["message"]["content"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--lora", type=Path, required=True, help="dossier cadrage-4b-lora téléchargé de Drive")
    ap.add_argument("--base", type=Path, required=True, help="dossier cadrage-4b-base téléchargé de Drive")
    ap.add_argument("--sums", type=Path, help="SHA256SUMS.txt téléchargé de Drive (recommandé)")
    a = ap.parse_args(argv)
    try:
        for kind, folder in (("base", a.base), ("lora", a.lora)):
            import_one(kind, folder, a.sums)
    except ExportError as e:
        print(f"REFUS : {e}")
        return 1
    print(json.dumps({"modeles": list(TAGS.values()), "suite": "lancer le banc avec eval/configs/B-4b-base.yaml et C-4b-lora.yaml"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
