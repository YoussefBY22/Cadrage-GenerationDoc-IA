"""Paquet d'entraînement Colab : pilote v2 relu + pilote v3 + rapports spéciaux de la Cour (2023-2026), invites refaites.

- les exemples v2 sont RE-RENDUS avec les fonctions actuelles de l'application (`v2_rerender`) ;
- les exemples v3 et ceux des rapports de la Cour (`eca_build`) sont reconstruits depuis les sources publiques ;
- chaque exemple repasse le vérificateur ; les réponses suivent l'ordre des propriétés de leur schéma ;
- séparation entraînement / validation / test PAR RAPPORT SOURCE (un rapport et ses réponses = un groupe) ;
- le paquet (`cadrage-donnees-publiques.zip`) ne contient que des documents publics sous licence ouverte ;
  son SHA-256 est écrit dans le carnet Colab et vérifié avant tout entraînement.

Usage :
    python -m training.dataset.assemble --v2 pilote-30-relu.jsonl --sources-dir DOSSIER_V3 --eca-dir DOSSIER_ECA --out-dir SORTIE
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from app.generation.llm_schemas import LLMFindings, LLMSection, LLMStance

from training.dataset import eca_build, schema_order, v2_rerender, v3_build
from training.dataset.v3_sources import SOURCES, source_text

# Groupes (rapport + réponses) mis de côté ; le reste est tiré par empreinte, sauf les groupes imposés ci-dessous.
TEST_V2 = {"ue-52022SC0349", "ue-52020SC0544"}
FORCED_TEST = {"eca-sr-2024-26", "eca-sr-2026-13"}
FORCED_VAL = {"ue-52021SC0379", "eca-sr-2024-27"}
MIN_TEST = {"total": 70, "conflit": 18, "refus": 12}
VAL_SIZE = 24
CAPS = {"feuille_de_route": 1, "extraction": 2, "position": 2, "conflit": 1, "refus": 1}
ZIP_NAME = "cadrage-donnees-publiques.zip"
OPEN = ("CC BY", "Décision 2011/833/UE", "Licence Ouverte")
TASK_OF_KIND = {"feuille de route": "feuille_de_route", "extraction de constats": "extraction",
                "divergence entre deux sources": "divergence", "termes de référence": "redaction_tdr",
                "cahier des charges": "redaction_cdc"}


def group_of(source: str) -> str:
    """Un rapport et ses réponses de la Commission forment un seul groupe (jamais des deux côtés)."""
    return "eca-sr-" + source[len("eca-rep-sr-"):] if source.startswith("eca-rep-sr-") else source


def task_of(meta: dict) -> str:
    if meta.get("task_type"):
        return meta["task_type"]
    return "refus" if "efus" in meta.get("kind", "") else TASK_OF_KIND.get(meta.get("kind", ""), "autre")


def pick(candidates: list[dict], seed: int = 11) -> list[dict]:
    """Au plus ``CAPS`` exemples par rapport et par tâche, tirés avec une graine fixe."""
    by: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for e in candidates:
        by[(e["meta"]["source"], e["meta"]["task_type"])].append(e)
    out: list[dict] = []
    for key in sorted(by):
        rng = random.Random(f"{seed}-{key}")
        items = by[key]
        rng.shuffle(items)
        out += items[:CAPS[key[1]]]
    return out


def assign_splits(rows: list[dict]) -> None:
    """Groupes de test : imposés, puis tirés par empreinte jusqu'aux minimums ; validation de même."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[group_of(r["meta"]["source"])].append(r)
    split = {g: "train" for g in groups}
    for g in groups:
        if g in FORCED_TEST or g in TEST_V2 or any(SOURCES.get(r["meta"]["source"], {}).get("test") for r in groups[g]):
            split[g] = "test"
        elif g in FORCED_VAL:
            split[g] = "val"

    def tally(part: str) -> Counter:
        c: Counter = Counter()
        for g, s in split.items():
            if s == part:
                for r in groups[g]:
                    c["total"] += 1
                    c[task_of(r["meta"])] += 1
        return c

    order = sorted((g for g in groups if split[g] == "train"), key=lambda g: hashlib.sha256(g.encode()).hexdigest())
    for g in order:
        t = tally("test")
        if all(t[k] >= v for k, v in MIN_TEST.items()):
            break
        split[g] = "test"
    for g in order:
        if split[g] != "train":
            continue
        if tally("val")["total"] >= VAL_SIZE:
            break
        split[g] = "val"
    for r in rows:
        r["meta"]["split"] = split[group_of(r["meta"]["source"])]


def build(v2_path: Path, sources_dir: Path, eca_dir: Path | None = None, skipped: list[str] | None = None) -> list[dict]:
    texts = {sid: source_text(sources_dir, sid) for sid in SOURCES}
    rows = v2_rerender.load_v2(v2_path, skipped)
    rows += [{"messages": e["messages"], "meta": {**e["meta"], "lot": "pilote-v3"}}
             for e in v3_build.build_all(texts)]
    for r in rows:
        r["meta"].setdefault("task_type", task_of(r["meta"]))
    if eca_dir is not None:
        cands: list[dict] = []
        for report in eca_build.load_reports(eca_dir):
            cands += eca_build.build_report(report)
        rows += pick(cands)
    assign_splits(rows)
    return rows


def _model(answer: dict):
    return LLMFindings if "findings" in answer else LLMStance if "stance" in answer else LLMSection


def check(rows: list[dict]) -> list[str]:
    """Défauts bloquants : licence, vérificateur, ordre des propriétés, invite non reproductible, groupe des deux côtés."""
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
        if not schema_order.is_ordered(_model(answer), answer):
            bad.append(f"{m['id']} : les propriétés de la réponse ne suivent pas l'ordre du schéma")
        if v3_build.rerender(r) != r["messages"][1]["content"]:
            bad.append(f"{m['id']} : l'invite ne se reproduit pas à l'identique")
    sides: dict[str, set[str]] = {}
    for r in rows:
        sides.setdefault(group_of(r["meta"]["source"]), set()).add(r["meta"]["split"])
    bad += [f"rapport des deux côtés : {s} {sorted(v)}" for s, v in sides.items() if len(v) > 1]
    return bad


def counts(rows: list[dict]) -> dict:
    out: dict = {"total": len(rows)}
    for part in ("train", "val", "test"):
        sel = [r for r in rows if r["meta"]["split"] == part]
        out[part] = {"exemples": len(sel), "documents": len({group_of(r["meta"]["source"]) for r in sel}),
                     "par_tache": dict(sorted(Counter(task_of(r["meta"]) for r in sel).items())),
                     "par_lot": dict(sorted(Counter(r["meta"]["lot"] for r in sel).items())),
                     "par_etiquette_position": dict(sorted(Counter(
                         r["meta"]["etiquette"] for r in sel if r["meta"].get("etiquette")).items()))}
    return out


def write_package(rows: list[dict], out_dir: Path, reports: list[dict] | None = None) -> dict:
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
        "rapports_cour": [{k: v for k, v in rep.items() if k in ("id", "url", "sha256", "year", "number", "reponse")}
                          for rep in (reports or [])],
        "documents": {s: {"titre": SOURCES[s]["titre"] if s in SOURCES else next(
            r["meta"]["source_titre"] for r in rows if r["meta"]["source"] == s),
            "licence": next(r["meta"]["licence"] for r in rows if r["meta"]["source"] == s),
            "split": next(r["meta"]["split"] for r in rows if r["meta"]["source"] == s)} for s in sources},
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
    ap.add_argument("--eca-dir", type=Path, help="dossier de eca_fetch (rapports spéciaux 2023-2026)")
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    skipped: list[str] = []
    rows = build(a.v2, a.sources_dir, a.eca_dir, skipped)
    for line in skipped:
        print("ÉCARTÉ (v2) :", line)
    bad = check(rows)
    if bad:
        raise SystemExit("REFUS :\n" + "\n".join(bad[:40]))
    reports = eca_build.load_reports(a.eca_dir) if a.eca_dir else []
    used = {r["meta"]["source"] for r in rows}
    print(json.dumps(write_package(rows, a.out_dir, [x for x in reports if x["id"] in used]), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
