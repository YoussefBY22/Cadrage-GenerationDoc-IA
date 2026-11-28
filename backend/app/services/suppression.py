"""Suppression d'un dossier (avec tout son contenu) ou d'un seul document.

Le journal d'audit est conservé : il trace la suppression elle-même. L'entrepôt BI n'est pas touché ;
il reflète l'application au dernier chargement (ETL).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import Engine, delete, select, update

from app.storage import schema as s


def _runs(c, dossier_id: str) -> list[str]:
    return list(c.execute(select(s.generation_runs.c.id).where(
        s.generation_runs.c.dossier_id == dossier_id)).scalars())


def dossier_counts(engine: Engine, dossier_id: str) -> dict:
    """Ce que la suppression emporte, pour la confirmation affichée à l'utilisateur."""
    with engine.connect() as c:
        def n(table, col=None):
            col = col if col is not None else table.c.dossier_id
            return len(c.execute(select(next(iter(table.c))).where(col == dossier_id)).all())
        return {"documents": n(s.documents), "findings": n(s.findings),
                "deliverables": n(s.deliverables), "recommendations": n(s.audit_recommendations),
                "decisions": n(s.decisions)}


def delete_dossier(engine: Engine, dossier_id: str) -> dict:
    counts = dossier_counts(engine, dossier_id)
    with engine.begin() as c:
        paths = list(c.execute(select(s.documents.c.stored_path).where(
            s.documents.c.dossier_id == dossier_id)).scalars())
        dels = list(c.execute(select(s.deliverables.c.id).where(
            s.deliverables.c.dossier_id == dossier_id)).scalars())
        chunks = select(s.chunks.c.id).where(s.chunks.c.dossier_id == dossier_id)
        runs = _runs(c, dossier_id)
        if runs:
            c.execute(delete(s.retrieval_hits).where(s.retrieval_hits.c.run_id.in_(runs)))
            c.execute(delete(s.verification_results).where(s.verification_results.c.run_id.in_(runs)))
        if dels:
            for t in (s.deliverable_versions, s.section_comments, s.state_transitions, s.exports):
                c.execute(delete(t).where(t.c.deliverable_id.in_(dels)))
        c.execute(delete(s.injection_alerts).where(s.injection_alerts.c.chunk_id.in_(chunks)))
        for t in (s.generation_runs, s.report_checks, s.audit_recommendations, s.findings, s.priorities,
                  s.existing_projects, s.decisions, s.context_sheets, s.dossier_profiles, s.chunks,
                  s.deliverables, s.documents, s.dossier_members):
            c.execute(delete(t).where(t.c.dossier_id == dossier_id))
        c.execute(delete(s.dossiers).where(s.dossiers.c.id == dossier_id))
    for p in paths:
        _remove_file(p)
        parent = Path(p).parent
        if parent.name == dossier_id:
            shutil.rmtree(parent, ignore_errors=True)
    return counts


def document_counts(engine: Engine, document_id: str) -> dict:
    with engine.connect() as c:
        doc = c.execute(select(s.documents).where(s.documents.c.id == document_id)).first()
        ids = set(c.execute(select(s.chunks.c.id).where(s.chunks.c.document_id == document_id)).scalars())
        only = touched = 0
        for f in c.execute(select(s.findings.c.source_ids).where(s.findings.c.dossier_id == doc.dossier_id)):
            src = set(f.source_ids or [])
            if src and src <= ids:
                only += 1
            elif src & ids:
                touched += 1
        recs = len(c.execute(select(s.audit_recommendations.c.id).where(
            s.audit_recommendations.c.document_id == document_id)).all())
    return {"passages": len(ids), "findings": only, "findings_partial": touched, "recommendations": recs}


def delete_document(engine: Engine, document_id: str) -> dict:
    """Supprime le document, ses passages, ses recommandations, et les constats qui ne reposaient que sur lui.
    Un constat appuyé aussi sur un autre document perd seulement les références à celui-ci."""
    counts = document_counts(engine, document_id)
    with engine.begin() as c:
        doc = c.execute(select(s.documents).where(s.documents.c.id == document_id)).first()
        ids = set(c.execute(select(s.chunks.c.id).where(s.chunks.c.document_id == document_id)).scalars())
        for f in c.execute(select(s.findings.c.id, s.findings.c.source_ids).where(
                s.findings.c.dossier_id == doc.dossier_id)).all():
            src = list(f.source_ids or [])
            rest = [x for x in src if x not in ids]
            if src and not rest:
                c.execute(delete(s.findings).where(s.findings.c.id == f.id))
            elif len(rest) != len(src):
                c.execute(update(s.findings).where(s.findings.c.id == f.id).values(source_ids=rest))
        if ids:
            c.execute(delete(s.injection_alerts).where(s.injection_alerts.c.chunk_id.in_(ids)))
        c.execute(delete(s.audit_recommendations).where(s.audit_recommendations.c.document_id == document_id))
        c.execute(delete(s.report_checks).where(s.report_checks.c.document_id == document_id))
        c.execute(delete(s.chunks).where(s.chunks.c.document_id == document_id))
        c.execute(delete(s.documents).where(s.documents.c.id == document_id))
        shared = c.execute(select(s.documents.c.id).where(s.documents.c.stored_path == doc.stored_path)).first()
    if not shared:
        _remove_file(doc.stored_path)
    return {**counts, "dossier_id": doc.dossier_id}


def _remove_file(path: str | None) -> None:
    if path:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass
