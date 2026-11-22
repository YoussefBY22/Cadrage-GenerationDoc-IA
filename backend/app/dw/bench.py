"""Banc d'essai A/B/C/D dans l'entrepôt : résultats de `eval/results/*.json` et décision de 08 §6.

    python -m app.dw.bench eval/results/20261122-B-*.json

Le banc est séparé de la production : il ne dépend d'aucun client et ne suit aucun filtre du tableau
de bord. Un chargement remplace le précédent, car une comparaison n'a de sens qu'entre résultats
produits ensemble.
"""

import argparse
import json
from pathlib import Path

from sqlalchemy import Engine, delete, insert

from . import pilotage
from . import schema as dw
from .schema import bind_dw, create_dw


def bench_rows(results: list[dict], is_demo: bool) -> list[dict]:
    by = {r["config"][:1]: r for r in results}
    if len(by) != len(results) or not set(by) <= set("ABCD"):
        raise ValueError("un seul résultat par configuration A, B, C ou D est attendu")
    reference = by.get(pilotage.REFERENCE_CONFIG)
    rows = []
    for label, r in sorted(by.items()):
        values, metrics, versions = r.get("tpv_sections") or [], r["metrics"], r.get("versions") or {}
        low, high = pilotage.bootstrap_ci(values) if values else (None, None)
        decided = {"decision": "not_paired", "delta": None, "low": None, "high": None, "degraded": []}
        if label == pilotage.REFERENCE_CONFIG:
            decided["decision"] = "reference"
        elif reference:
            decided = pilotage.bench_decision(r, reference)

        def mean(key: str, m=metrics):
            return (m.get(key) or {}).get("mean")

        rows.append({
            "config_label": label, "model_name": str(versions.get("model") or "inconnu")[:120],
            "adapter": str(versions["adapter"])[:120] if versions.get("adapter") else None,
            "has_retrieval": bool(((r.get("params") or {}).get("retrieval") or {}).get("enabled")),
            "n_sections": len(values), "tpv": sum(values) / len(values) if values else None,
            "tpv_low": low, "tpv_high": high, "delta": decided["delta"], "delta_low": decided["low"],
            "delta_high": decided["high"], "decision": decided["decision"],
            "degraded": ",".join(decided["degraded"])[:120],
            "citation_validity": mean("citation_validity"), "number_fidelity": mean("number_fidelity"),
            "attack_success": mean("attack_success"), "latency_p95_ms": mean("latency_p95_ms"),
            "simulated": bool(r.get("simulation")), "is_demo": is_demo})
    return rows


def load_bench(engine: Engine, results: list[dict], *, is_demo: bool = False) -> int:
    create_dw(engine)
    rows = bench_rows(results, is_demo)
    with bind_dw(engine).begin() as c:
        c.execute(delete(dw.fact_bench))
        if rows:
            c.execute(insert(dw.fact_bench), rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Charge des résultats du banc d'essai dans l'entrepôt")
    parser.add_argument("results", nargs="+", help="un fichier JSON par configuration")
    args = parser.parse_args()
    from ..config import get_settings
    from ..storage.engine import make_engine

    results = [json.loads(Path(p).read_text(encoding="utf-8")) for p in args.results]
    print({"configurations": load_bench(make_engine(get_settings().storage_url), results)})


if __name__ == "__main__":
    main()
