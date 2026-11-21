"""Accès aux livrables, versions, commentaires, acquittements (au-dessus de SqlRepository).

Le Repository de B1 n'expose pas ces lectures : on utilise `repo.engine` et le schéma.
"""

from sqlalchemy import insert, select

from app.domain.generation import DeliverableContent
from app.domain.ids import new_id
from app.domain.verification import VerificationReport
from app.storage import schema as s
from app.verification.verifier import verify_section


def get_deliverable(repo, deliverable_id: str) -> dict | None:
    with repo.engine.connect() as c:
        row = c.execute(select(s.deliverables).where(s.deliverables.c.id == deliverable_id)).first()
    return dict(row._mapping) if row else None


def list_versions(repo, deliverable_id: str) -> list[dict]:
    t = s.deliverable_versions
    with repo.engine.connect() as c:
        rows = c.execute(select(t.c.version, t.c.origin, t.c.author_id, t.c.created_at,
                                t.c.content_sha256).where(t.c.deliverable_id == deliverable_id)
                         .order_by(t.c.version))
        return [{"version": r.version, "origin": r.origin, "author_id": r.author_id,
                 "created_at": r.created_at.isoformat() if r.created_at else None,
                 "content_sha256": r.content_sha256} for r in rows]


def version_author(repo, deliverable_id: str, version: int) -> str | None:
    t = s.deliverable_versions
    with repo.engine.connect() as c:
        return c.execute(select(t.c.author_id).where(
            t.c.deliverable_id == deliverable_id, t.c.version == version)).scalar()


def verify_content(repo, dossier_id: str, content: DeliverableContent,
                   support_threshold: float = 0.3) -> list[VerificationReport]:
    """Re-vérifie chaque section contre les passages du dossier (jamais d'autre dossier)."""
    known = {f.id for f in repo.list_findings(dossier_id)}
    reports = []
    for sec in content.sections:
        ids = sorted({i for sent in sec.sentences for i in sent.source_ids})
        passages = repo.get_chunks(dossier_id, ids) if ids else {}
        reports.append(verify_section(sec, passages, dossier_id=dossier_id,
                                      known_finding_ids=known,
                                      support_threshold=support_threshold,
                                      lang=content.language))
    return reports


def add_comment(repo, deliverable_id: str, section_key: str, user_id: str, text: str) -> str:
    cid = new_id("run")
    with repo.engine.begin() as c:
        c.execute(insert(s.section_comments).values(
            id=cid, deliverable_id=deliverable_id, section_key=section_key,
            user_id=user_id, text=text))
    return cid


def list_comments(repo, deliverable_id: str) -> list[dict]:
    t = s.section_comments
    with repo.engine.connect() as c:
        rows = c.execute(select(t).where(t.c.deliverable_id == deliverable_id)
                         .order_by(t.c.created_at, t.c.id))
        return [{"id": r.id, "section_key": r.section_key, "user_id": r.user_id, "text": r.text,
                 "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]


def list_audit(repo, object_id: str | None = None, limit: int = 500) -> list[dict]:
    t = s.audit_log
    stmt = select(t).order_by(t.c.id).limit(limit)
    if object_id:
        stmt = stmt.where(t.c.object_id == object_id)
    with repo.engine.connect() as c:
        return [{"id": r.id, "at": r.at.isoformat() if r.at else None, "user_id": r.user_id,
                 "action": r.action, "object_type": r.object_type, "object_id": r.object_id,
                 "details": r.details} for r in c.execute(stmt)]


def acknowledgements(repo, deliverable_id: str, version: int) -> set[tuple[str, int]]:
    """Acquittements (section, index de phrase ; -1 = refus de la section) de cette version."""
    rows = [a for a in list_audit(repo, deliverable_id, limit=100000)
            if a["action"] == "sentence.acknowledge" and a["details"].get("version") == version]
    return {(a["details"]["section_key"], a["details"]["sentence_index"]) for a in rows}
