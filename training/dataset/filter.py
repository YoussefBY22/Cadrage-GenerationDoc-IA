"""Filtrage des exemples candidats : seuls les exemples dont le TPV vaut 1 sont gardés.

TPV = taux de phrases vérifiées (`app.verification.verify_section`). Un refus (aucune phrase) est
gardé s'il est bien formé ; un piège est rejeté si la sortie contient le canari d'injection.
La méta « licence » est obligatoire. Usage :
python -m training.dataset.filter --inp candidates.jsonl --out filtered.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.domain.documents import Chunk
from app.domain.retrieval import Passage
from app.generation.llm_schemas import LLMFindings, LLMSection
from app.verification.verifier import resolve_labels, verify_section
from training.dataset.build import TRAIN_CANARY


def check_example(ex: dict) -> tuple[bool, str]:
    """Retourne (gardé, raison)."""
    meta = ex.get("meta") or {}
    if not str(meta.get("licence", "")).strip():
        return False, "licence manquante"
    if not meta.get("source"):
        return False, "source manquante"
    answer = ex["messages"][2]["content"]
    if meta.get("kind") == "piege" and TRAIN_CANARY in answer:
        return False, "la sortie suit l'injection"
    verif = ex.get("_verif")
    if not verif:
        return False, "données de vérification absentes"
    passages = [Passage(label=p["label"], chunk=Chunk.model_validate(p["chunk"]), score=1.0,
                        ranks={}) for p in verif["passages"]]
    try:
        data = json.loads(answer)
        if meta.get("kind") == "constats":
            parsed = LLMFindings.model_validate(data)
            labels = {p.label for p in passages}
            ok = parsed.status == "ok" and all(
                s in labels for f in parsed.findings for s in f.sources)
            return ok, "" if ok else "constat sans source valide"
        llm = LLMSection.model_validate(data)
    except ValueError:
        return False, "sortie non conforme au schéma"
    if llm.status == "insufficient_evidence":
        return (not llm.sentences and bool(llm.missing_evidence)), "refus mal formé"
    draft = resolve_labels(llm, passages, section_key="ex")
    report = verify_section(draft, {p.chunk.id: p.chunk for p in passages},
                            dossier_id=verif["dossier_id"])
    return (report.tpv == 1.0 and bool(report.checks)), f"TPV = {report.tpv:.2f}"


def filter_examples(candidates: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Garde les exemples valides, retire `_verif` ; renvoie aussi le décompte des rejets."""
    kept, rejects = [], {}
    for ex in candidates:
        ok, why = check_example(ex)
        if ok:
            kept.append({k: v for k, v in ex.items() if k != "_verif"})
        else:
            rejects[why] = rejects.get(why, 0) + 1
    return kept, rejects


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inp", type=Path, default=Path("training/data/candidates.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("training/data/filtered.jsonl"))
    args = ap.parse_args()
    cands = [json.loads(line) for line in args.inp.read_text(encoding="utf-8").splitlines()]
    kept, rejects = filter_examples(cands)
    args.out.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in kept),
                        encoding="utf-8")
    print(f"{len(kept)}/{len(cands)} gardés ; rejets : {rejects}")


if __name__ == "__main__":
    main()
