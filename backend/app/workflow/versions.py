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
    """Re-vérifie chaque section contre les passages du dossier (jamais d'autre dossier).

    Seuls les constats VALIDÉS sont connus : citer un constat non validé est un défaut de preuve.
    """
    known = {f.id for f in repo.list_findings(dossier_id, validated_only=True)}
    reports = []
    for sec in content.sections:
        ids = sorted({i for sent in sec.sentences for i in sent.source_ids})
        passages = repo.get_chunks(dossier_id, ids) if ids else {}
        reports.append(verify_section(sec, passages, dossier_id=dossier_id,
                                      known_finding_ids=known,
                                      support_threshold=support_threshold,
                                      lang=content.language))
    return reports


def initiative_issues(repo, dossier_id: str, content: DeliverableContent) -> list[dict]:
    """Initiatives d'une feuille de route dont le constat est absent, inconnu ou non validé.

    Une initiative approuvée doit reposer sur des constats qui existent dans CE dossier ET sont validés.
    """
    if content.roadmap is None:
        if content.type == "roadmap":
            return [{"initiative_id": None, "code": "ROADMAP_MISSING", "finding_id": None}]
        return []
    findings = {f.id: f for f in repo.list_findings(dossier_id)}
    out: list[dict] = []
    if content.type == "roadmap" and not content.roadmap.items:
        out.append({"initiative_id": None, "code": "EMPTY_ROADMAP", "finding_id": None})
    for item in content.roadmap.items:
        ini = item.initiative
        if not ini.finding_ids:
            out.append({"initiative_id": ini.id, "code": "INITIATIVE_WITHOUT_FINDING",
                        "finding_id": None})
        for fid in ini.finding_ids:
            if fid not in findings:
                out.append({"initiative_id": ini.id, "code": "UNKNOWN_FINDING", "finding_id": fid})
            elif not findings[fid].validated:
                out.append({"initiative_id": ini.id, "code": "FINDING_NOT_VALIDATED",
                            "finding_id": fid})
    return out


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
    """Acquittements (section, index de phrase ; -1 = refus de la section) de cette version.

    Un acquittement sans motif (ancien format) ne compte pas.
    """
    rows = [a for a in list_audit(repo, deliverable_id, limit=100000)
            if a["action"] == "sentence.acknowledge" and a["details"].get("version") == version
            and str(a["details"].get("reason") or "").strip()]
    return {(a["details"]["section_key"], a["details"]["sentence_index"]) for a in rows}


# --- verrou d'approbation ------------------------------------------------------------------------
# Un défaut de preuve ne s'acquitte pas : il se corrige. Les autres échecs exigent un motif.
NON_ACKNOWLEDGEABLE = frozenset({"UNKNOWN_SOURCE", "FOREIGN_SOURCE", "FACT_WITHOUT_SOURCE",
                                 "UNKNOWN_FINDING", "INSTRUCTION_ECHO"})


def unsupported_recommendations(content: DeliverableContent) -> set[tuple[str, int]]:
    """Recommandations sans source ni constat : à acquitter avec motif avant approbation."""
    return {(sec.section_key, i) for sec in content.sections for i, sn in enumerate(sec.sentences)
            if sn.kind == "recommendation" and not sn.source_ids and not sn.finding_ids}


def evidence_status(repo, dossier_id: str, content: DeliverableContent,
                    support_threshold: float = 0.3):
    """(rapports, phrases au défaut de preuve, phrases à acquitter) ; clés (section, index)."""
    reports = verify_content(repo, dossier_id, content, support_threshold)
    hard: set[tuple[str, int]] = set()
    soft: set[tuple[str, int]] = set(unsupported_recommendations(content))
    for sec, rep in zip(content.sections, reports, strict=True):
        for issue in rep.issues:
            if issue.code in NON_ACKNOWLEDGEABLE:
                hard.add((sec.section_key, issue.sentence_index))
        for ck in rep.checks:
            if ck.status == "failed":
                soft.add((sec.section_key, ck.index))
    return reports, hard, soft - hard


def evidence_problems(repo, dossier_id: str, content: DeliverableContent) -> list[str]:
    """Défauts qui interdisent l'export, même d'un livrable approuvé avant ce contrôle."""
    _, hard, _ = evidence_status(repo, dossier_id, content)
    out = [f"phrase {i + 1} de « {key} » sans preuve valide" for key, i in sorted(hard)]
    out += [f"initiative {x['initiative_id'] or '—'} : {x['code']}"
            for x in initiative_issues(repo, dossier_id, content)]
    return out
