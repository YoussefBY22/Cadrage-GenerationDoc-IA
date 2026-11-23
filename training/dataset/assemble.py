"""Paquet d'entraînement Colab : pilote v2 relu (30) + pilote v3 (25), invites refaites, séparées par document.

- les 30 exemples v2 sont RE-RENDUS avec les fonctions actuelles de l'application (`v2_rerender`) ;
- les 25 exemples v3 sont reconstruits depuis les sources publiques (`v3_build`), donc avec la version actuelle
  des prompts et du vérificateur ;
- chaque exemple repasse le vérificateur ; séparation entraînement / validation / test PAR DOCUMENT SOURCE ;
- le paquet (`cadrage-donnees-publiques.zip`) ne contient que des documents publics sous licence ouverte,
  son SHA-256 est écrit dans le carnet Colab et vérifié avant tout entraînement.

Usage :
    python -m training.dataset.assemble --v2 pilote-30-relu.jsonl --sources-dir DOSSIER --out-dir SORTIE
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

from app.generation.llm_schemas import LLMFindings, LLMSection

from training.dataset import schema_order, v2_rerender, v3_build
from training.dataset.v3_sources import SOURCES, source_text

# Documents mis de côté (le reste entraîne). Les documents de test v3 viennent du manifeste (`test: True`).
TEST_V2 = {"ue-52022SC0349", "ue-52020SC0544"}
VAL = {"ue-52021SC0379", "eca-rep-sr-2024-27"}
ZIP_NAME = "cadrage-donnees-publiques.zip"
OPEN = ("CC BY", "Décision 2011/833/UE", "Licence Ouverte")


def split_of(source: str) -> str:
    if source in VAL:
        return "val"
    if source in TEST_V2 or SOURCES.get(source, {}).get("test"):
        return "test"
    return "train"


def build(v2_path: Path, sources_dir: Path, skipped: list[str] | None = None) -> list[dict]:
    texts = {sid: source_text(sources_dir, sid) for sid in SOURCES}
    rows = v2_rerender.load_v2(v2_path, skipped)
    rows += [{"messages": e["messages"], "meta": {**e["meta"], "lot": "pilote-v3"}}
             for e in v3_build.build_all(texts)]
    for r in rows:
        r["meta"]["split"] = split_of(r["meta"]["source"])
    return rows


def check(rows: list[dict]) -> list[str]:
    """Défauts bloquants : licence, vérificateur, invite non reproductible, document des deux côtés."""
    bad: list[str] = []
    ids = Counter(r["meta"]["id"] for r in rows)
    bad += [f"identifiant en double : {i}" for i, n in ids.items() if n > 1]
    for r in rows:
        m = r["meta"]
        if not str(m.get("licence", "")).startswith(OPEN) or not str(m.get("licence_preuve", "")).startswith("https://"):
            bad.append(f"{m['id']} : licence ou preuve manquante")
        tpv, blocking = v3_build.verify_example(r)
        if blocking or tpv < 1:
            bad.append(f"{m['id']} : le vérificateur refuse ({blocking}, tpv {tpv})")
        answer = json.loads(r["messages"][2]["content"])
        if not schema_order.is_ordered(LLMFindings if "findings" in answer else LLMSection, answer):
            bad.append(f"{m['id']} : les propriétés de la réponse ne suivent pas l'ordre du schéma")
        if v3_build.rerender(r) != r["messages"][1]["content"]:
            bad.append(f"{m['id']} : l'invite ne se reproduit pas à l'identique")
    sides: dict[str, set[str]] = {}
    for r in rows:
        sides.setdefault(r["meta"]["source"], set()).add(r["meta"]["split"])
    bad += [f"document des deux côtés : {s} {sorted(v)}" for s, v in sides.items() if len(v) > 1]
    return bad


def counts(rows: list[dict]) -> dict:
    out: dict = {"total": len(rows)}
    for part in ("train", "val", "test"):
        sel = [r for r in rows if r["meta"]["split"] == part]
        out[part] = {"exemples": len(sel), "documents": len({r["meta"]["source"] for r in sel}),
                     "par_type": dict(sorted(Counter(r["meta"]["kind"] for r in sel).items())),
                     "par_lot": dict(sorted(Counter(r["meta"]["lot"] for r in sel).items()))}
    return out


def write_package(rows: list[dict], out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {}
    for part in ("train", "val", "test"):
        body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows if r["meta"]["split"] == part)
        files[f"{part}.jsonl"] = body.encode("utf-8")
    sources = sorted({r["meta"]["source"] for r in rows})
    manifest = {
        "contenu": "documents publics sous licence ouverte, aucun document client",
        "effectifs": counts(rows),
        "licences": sorted({r["meta"]["licence"] for r in rows}),
        "documents": {s: {"titre": SOURCES[s]["titre"] if s in SOURCES else next(
            r["meta"]["source_titre"] for r in rows if r["meta"]["source"] == s),
            "licence": next(r["meta"]["licence"] for r in rows if r["meta"]["source"] == s),
            "split": split_of(s)} for s in sources},
        "sha256": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()},
    }
    files["MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    archive = out_dir / ZIP_NAME
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as z:  # sans compression : octets reproductibles
        for name in sorted(files):
            z.writestr(zipfile.ZipInfo(name, (2026, 11, 23, 0, 0, 0)), files[name])
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out_dir / f"{ZIP_NAME}.sha256").write_text(f"{sha}  {ZIP_NAME}\n", encoding="utf-8", newline="\n")
    return {"zip": str(archive), "sha256": sha, **manifest["effectifs"]}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--v2", type=Path, required=True, help="pilote-30-relu.jsonl")
    ap.add_argument("--sources-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    skipped: list[str] = []
    rows = build(a.v2, a.sources_dir, skipped)
    for line in skipped:
        print("ÉCARTÉ (v2) :", line)
    bad = check(rows)
    if bad:
        raise SystemExit("REFUS :\n" + "\n".join(bad))
    print(json.dumps(write_package(rows, a.out_dir), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
