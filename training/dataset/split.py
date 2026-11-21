"""Découpage 80/10/10 **par document source** : aucun document n'est à la fois en train et en test.

Usage : python -m training.dataset.split --inp filtered.jsonl --out-dir training/data --seed 7
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def split_by_source(examples: list[dict], seed: int = 7,
                    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1)) -> dict[str, list[dict]]:
    """Répartit les *sources* (pas les exemples) ; chaque jeu non vide dès 3 sources."""
    sources = sorted({e["meta"]["source"] for e in examples})
    random.Random(seed).shuffle(sources)
    n = len(sources)
    n_val = max(1, round(n * ratios[1])) if n >= 3 else 0
    n_test = max(1, round(n * ratios[2])) if n >= 3 else 0
    groups = {"test": sources[:n_test], "val": sources[n_test:n_test + n_val],
              "train": sources[n_test + n_val:]}
    return {name: [e for e in examples if e["meta"]["source"] in set(srcs)]
            for name, srcs in groups.items()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inp", type=Path, default=Path("training/data/filtered.jsonl"))
    ap.add_argument("--out-dir", type=Path, default=Path("training/data"))
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    ex = [json.loads(line) for line in args.inp.read_text(encoding="utf-8").splitlines()]
    parts = split_by_source(ex, args.seed)
    for name, items in parts.items():
        (args.out_dir / f"{name}.jsonl").write_text(
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in items), encoding="utf-8")
        print(f"{name}: {len(items)} exemples")


if __name__ == "__main__":
    main()
