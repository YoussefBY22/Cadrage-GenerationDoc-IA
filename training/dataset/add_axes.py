"""Paquet v5 = paquet v4 (inchangé) + tâche « axes », avec le MÊME découpage par rapport.

Un rapport déjà en test (ou en validation) dans v4 y reste pour ses exemples « axes » : aucune fuite, et les
résultats v4 / v5 restent comparables. Un rapport absent de v4 va en entraînement.

    python -m training.dataset.add_axes --v4 training/colab/cadrage-donnees-publiques.zip \
        --eca-dir DOSSIER_ECA --out-dir SORTIE
"""

from __future__ import annotations

import argparse
import json
import random
import zipfile
from collections import Counter
from pathlib import Path

from training.dataset import assemble, eca_axes, eca_build


def load_v4(path: Path) -> list[dict]:
    z = zipfile.ZipFile(path)
    return [json.loads(line) for part in ("train", "val", "test")
            for line in z.read(f"{part}.jsonl").decode("utf-8").splitlines() if line.strip()]


def axes_rows(reports: list[dict], split_of: dict[str, str], seed: int = 7) -> list[dict]:
    rows = []
    for rep in reports:
        rng = random.Random(f"{seed}-{rep['id']}-axes")
        exs = [e for e in eca_axes.build_examples(rep, rng) if not eca_axes.check(e, rep["text"])]
        for e in exs[:assemble.CAPS["axes"]]:
            e["meta"]["split"] = split_of.get(assemble.group_of(rep["id"]), "train")
            rows.append(e)
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--v4", type=Path, required=True)
    ap.add_argument("--eca-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    v4 = load_v4(a.v4)
    split_of = {assemble.group_of(r["meta"]["source"]): r["meta"]["split"] for r in v4}
    reports = eca_build.load_reports(a.eca_dir)
    new = axes_rows(reports, split_of)
    bad = assemble.check(new)
    sides: dict[str, set[str]] = {}
    for r in v4 + new:
        sides.setdefault(assemble.group_of(r["meta"]["source"]), set()).add(r["meta"]["split"])
    bad += [f"rapport des deux côtés : {s}" for s, v in sides.items() if len(v) > 1]
    if bad:
        raise SystemExit("REFUS :\n" + "\n".join(bad[:40]))
    print("axes par jeu :", dict(Counter(r["meta"]["split"] for r in new)))
    used = {r["meta"]["source"] for r in v4 + new}
    print(json.dumps(assemble.write_package(v4 + new, a.out_dir, [x for x in reports if x["id"] in used]),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
