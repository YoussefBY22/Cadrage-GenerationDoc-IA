"""Rapport comparatif : `python -m eval.harness.report eval/results/*.json [--csv out.csv]`.

Tableau Markdown + CSV (pour l'entrepôt) + règle de décision C vs B de 08 §6.
"""

import argparse
import csv
import io
import json
from pathlib import Path

from eval.harness.bootstrap import paired_diff_ci

COLUMNS = [
    ("recall_at_k", "Rappel@k"), ("mrr", "MRR"), ("tpv", "TPV"),
    ("citation_validity", "Citations valides"), ("number_fidelity", "Fidélité chiffres"),
    ("structure_validity", "Structure 1er essai"), ("finding_coverage", "Couverture constats"),
    ("dependency_cycles", "Cycles"), ("dependency_recall", "Rappel dépendances"),
    ("missed_refusals", "Refus manqués"), ("false_refusals", "Faux refus"),
    ("attack_success", "Réussite d'attaque"), ("latency_p50_ms", "Latence p50 (ms)"),
    ("latency_p95_ms", "Latence p95 (ms)"), ("tokens_per_s", "Jetons/s"), ("vram_max_mb", "VRAM max (Mo)"),
]
# Métriques « de sécurité » : C ne doit en dégrader aucune par rapport à B (sens : plus haut = mieux ?)
SECURITY = [("attack_success", False), ("citation_validity", True), ("number_fidelity", True),
            ("missed_refusals", False)]
EPS = 1e-9


def load(paths: list[str | Path]) -> list[dict]:
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]


def _val(res: dict, key: str) -> float | None:
    return (res["metrics"].get(key) or {}).get("mean")


def _fmt(res: dict, key: str) -> str:
    m = res["metrics"].get(key) or {}
    if m.get("mean") is None:
        return "—"
    sd = m.get("sd")
    mean = m["mean"]
    txt = f"{mean:.0f}" if key.endswith(("_ms", "_mb")) else f"{mean:.3f}"
    return f"{txt} ± {sd:.3f}" if sd and key not in ("recall_at_k", "mrr") else txt


def decide_c_vs_b(c: dict, b: dict, n: int = 1000, seed: int = 0) -> dict:
    """C est retenue seulement si l'IC95 de (TPV_C - TPV_B) est > 0 ET aucune métrique de sécurité
    ne se dégrade (08 §6). Les deux séries de sections doivent être appariées."""
    lo, hi = paired_diff_ci(c["tpv_sections"], b["tpv_sections"], n, seed)
    degraded = []
    for key, higher_better in SECURITY:
        vc, vb = _val(c, key), _val(b, key)
        if vc is None or vb is None:
            continue
        worse = vc < vb - EPS if higher_better else vc > vb + EPS
        if worse:
            degraded.append(key)
    return {"ci_low": lo, "ci_high": hi, "degraded": degraded, "retain_c": lo > 0 and not degraded}


def to_markdown(results: list[dict]) -> str:
    lines = []
    if any(r.get("simulation") for r in results):
        lines += ["> **Simulation : sans valeur scientifique** (FakeProvider).", ""]
    head = ["Config", "Sections", *[label for _, label in COLUMNS], "TPV IC95"]
    lines += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in results:
        ci = r.get("tpv_ci95") or [0, 0]
        row = [r["config"], str(r.get("n_sections", "")), *[_fmt(r, k) for k, _ in COLUMNS],
               f"[{ci[0]:.3f} ; {ci[1]:.3f}]"]
        lines.append("| " + " | ".join(row) + " |")
    by = {r["config"]: r for r in results}
    if "B" in by and "C" in by:
        d = decide_c_vs_b(by["C"], by["B"])
        verdict = "C retenue" if d["retain_c"] else "C non retenue"
        degraded = ", ".join(d["degraded"]) or "aucune"
        interval = f"[{d['ci_low']:.3f} ; {d['ci_high']:.3f}]"
        lines += ["", (f"**Décision C vs B** : IC95 de TPV_C − TPV_B = {interval} ; "
                       f"sécurité dégradée : {degraded} → **{verdict}**.")]
    return "\n".join(lines) + "\n"


def to_csv(results: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["config", "date", "simulation", "seeds", "metric", "mean", "sd"])
    for r in results:
        for key, _ in COLUMNS:
            m = r["metrics"].get(key) or {}
            w.writerow([r["config"], r["date"], r.get("simulation", False), len(r["seeds"]), key,
                        m.get("mean", ""), m.get("sd", "")])
    return buf.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--csv", default=None, help="écrit aussi le CSV comparatif")
    args = ap.parse_args()
    results = load(args.files)
    print(to_markdown(results))
    if args.csv:
        Path(args.csv).write_text(to_csv(results), encoding="utf-8")


if __name__ == "__main__":
    main()
