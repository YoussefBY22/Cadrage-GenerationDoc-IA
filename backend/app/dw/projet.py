"""Entrepôt : fiche projet, recommandations des rapports, constats par axe, feuille de route, entraînements.

Reconstruit à chaque ETL (situation courante, pas d'historique). Le tableau de bord lit la version
**corrigée** par le consultant : supprimées et fusionnées ne comptent pas.
"""

from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy import delete, select

from ..services import projet as svc
from ..storage import schema as op
from . import schema as dw

NON_RATTACHE = "Non rattaché à un axe"
NOUVELLES = ("dossier_profiles", "report_checks", "audit_recommendations", "training_runs",
             "training_eval_points", "training_task_scores")
TABLES = (dw.fact_audit_recommendation, dw.fact_report_check, dw.fact_finding, dw.fact_initiative,
          dw.dim_project, dw.fact_training_point, dw.fact_training_score, dw.fact_training_run)


def _cle(iso: str | None) -> int | None:
    return int(iso.replace("-", "")) if iso else None


def _libelle(nom: str, rang: int) -> str:
    """Nom lisible du rapport : le fichier sans extension, coupé au mot (le rang si le nom est vide)."""
    base = nom.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip() or f"Rapport {rang}"
    return base if len(base) <= 44 else base[:43].rsplit(" ", 1)[0] + "…"


def _contenu(v) -> dict:
    return v if isinstance(v, dict) else json.loads(v)


def refresh(loader, c, o) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    if o.engine.dialect.name == "sqlite":  # base antérieure à ces tables ; PostgreSQL : migration 0005
        op.metadata.create_all(o.engine, tables=[op.metadata.tables[n] for n in NOUVELLES])
    for t in TABLES:
        c.execute(delete(t))
    demo = {d: bool(r.is_demo) for d, r in loader.dossiers.items()}

    # fiche projet
    profils = {r.dossier_id: r for r in o.execute(select(op.dossier_profiles))}
    docs = list(o.execute(select(op.documents.c.id, op.documents.c.dossier_id, op.documents.c.role,
                                 op.documents.c.filename, op.documents.c.pages)))
    for did, mk in loader.mission_keys.items():
        p = profils.get(did)
        siens = [d for d in docs if d.dossier_id == did]
        c.execute(dw.dim_project.insert().values(
            mission_key=mk, request_summary=(p.request_summary if p else "")[:200],
            start_date_key=_cle(p.start_date) if p else None, end_date_key=_cle(p.end_date) if p else None,
            logo=p.logo if p else None, documents=len(siens),
            audit_reports=sum(1 for d in siens if d.role == svc.RAPPORT), is_demo=demo[did]))
        counts["dim_project"] += 1

    # recommandations et contrôle de cohérence, rapport par rapport (même règle que l'application)
    for did, mk in loader.mission_keys.items():
        vue = svc.overview(o.engine, did)
        for i, rap in enumerate(vue["reports"], 1):
            dk = loader.doc_keys.get(rap["document_id"])
            if dk is None:
                continue
            ctl = rap["check"]
            actives = [r for r in rap["recommendations"] if r["status"] in svc.ACTIFS]
            c.execute(dw.fact_report_check.insert().values(
                document_key=dk, mission_key=mk, report_label=_libelle(rap["filename"], i),
                pages=rap["pages"], expected=ctl["expected"], extracted=ctl["extracted"],
                validated=sum(1 for r in actives if r["status"] == "validated"),
                missing=len(ctl["missing"]), duplicates=len(ctl["duplicates"]),
                missing_list=", ".join(map(str, ctl["missing"]))[:200], status=ctl["status"],
                is_demo=demo[did]))
            counts["fact_report_check"] += 1
            for r in rap["recommendations"]:
                c.execute(dw.fact_audit_recommendation.insert().values(
                    recommendation_id=r["id"], mission_key=mk, document_key=dk, number=r["number"],
                    page=r["page"], status=r["status"], origin=r["origin"], is_demo=demo[did]))
                counts["fact_audit_recommendation"] += 1

    # feuille de route : la plus récente du dossier ; un constat prend l'axe de l'initiative qui le cite
    feuilles = {}
    for d in o.execute(select(op.deliverables).where(op.deliverables.c.type == "roadmap")
                       .order_by(op.deliverables.c.created_at)):
        feuilles[d.dossier_id] = d
    axe_du_constat: dict[str, str] = {}
    for did, d in feuilles.items():
        if did not in loader.mission_keys:
            continue
        v = o.execute(select(op.deliverable_versions.c.content).where(
            op.deliverable_versions.c.deliverable_id == d.id)
            .order_by(op.deliverable_versions.c.version.desc())).first()
        items = (_contenu(v.content).get("roadmap") or {}).get("items", []) if v else []
        for it in items:
            ini = it.get("initiative", {})
            axe = (ini.get("axis") or NON_RATTACHE)[:200]
            constats = list(ini.get("finding_ids", [])) + list(ini.get("auto_finding_ids", []))
            for f in constats:
                axe_du_constat.setdefault(f, axe)
            c.execute(dw.fact_initiative.insert().values(
                initiative_id=ini.get("id", "")[:32], mission_key=loader.mission_keys[did], axis=axe,
                wave=it.get("wave"), rank=it.get("rank"), findings=len(set(constats)), is_demo=demo[did]))
            counts["fact_initiative"] += 1

    for f in o.execute(select(op.findings.c.id, op.findings.c.dossier_id, op.findings.c.severity,
                              op.findings.c.validated)):
        if f.dossier_id not in loader.mission_keys:
            continue
        c.execute(dw.fact_finding.insert().values(
            finding_id=f.id, mission_key=loader.mission_keys[f.dossier_id], severity=f.severity,
            axis=axe_du_constat.get(f.id, NON_RATTACHE), validated=bool(f.validated), is_demo=demo[f.dossier_id]))
        counts["fact_finding"] += 1

    # registre des entraînements
    for r in svc.list_trainings(o.engine):
        c.execute(dw.fact_training_run.insert().values(
            run_id=r["id"], label=r["label"], run_date_key=_cle(r["run_date"]), platform=r["platform"],
            gpu=r["gpu"], examples=r["examples"], test_examples=r["test_examples"],
            duration_min=r["duration_min"], stop_step=r["stop_step"], best_step=r["best_step"],
            best_val_loss=r["best_val_loss"], adopted=bool(r["adopted"]), outcome=r["outcome"]))
        for p in r["validation"]:
            c.execute(dw.fact_training_point.insert().values(
                run_id=r["id"], step=p["step"], val_loss=p["val_loss"], is_best=p["step"] == r["best_step"]))
        for s in r["tests"]:
            c.execute(dw.fact_training_score.insert().values(run_id=r["id"], **s))
        counts["fact_training_run"] += 1
    return dict(counts)
