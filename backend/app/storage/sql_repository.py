"""Implémentation unique du dépôt : SQLAlchemy 2 Core, indépendante du dialecte."""

import hashlib
import json
from collections.abc import Iterator

from sqlalchemy import Engine, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from ..domain.coeur import ExistingProject, Priority
from ..domain.documents import Chunk, ParsedDocument
from ..domain.generation import DeliverableContent, Finding
from ..domain.ids import new_id
from ..domain.retrieval import Passage
from ..domain.verification import VerificationReport
from . import schema as s
from .repository import DuplicateDocumentError
from .vector_search import build_vector_search

_RUN_COLUMNS = {c.name for c in s.generation_runs.columns}


def _chunk(row) -> Chunk:
    return Chunk(
        id=row.id, document_id=row.document_id, dossier_id=row.dossier_id, ordinal=row.ordinal,
        text=row.text, page_start=row.page_start, page_end=row.page_end,
        section_path=tuple(row.section_path or ()), token_estimate=row.token_estimate,
        injection_flags=list(row.injection_flags or []))


def _priority(row) -> Priority:
    return Priority(
        id=row.id, dossier_id=row.dossier_id, title=row.title, description=row.description or "",
        rank=row.rank, status=row.status, source_ids=list(row.source_ids or []),
        author_id=row.author_id, validated_by=row.validated_by, validated_at=row.validated_at,
        created_at=row.created_at)


def _project(row) -> ExistingProject:
    return ExistingProject(
        id=row.id, dossier_id=row.dossier_id, title=row.title, state=row.state,
        duration_weeks=row.duration_weeks, depends_on=list(row.depends_on or []),
        source_ids=list(row.source_ids or []), author_id=row.author_id, created_at=row.created_at)


class SqlRepository:
    """Toutes les lectures de passages sont filtrées par `dossier_id` (aucune fuite entre dossiers)."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self._vectors = build_vector_search(engine)

    # --- dossiers et utilisateurs -------------------------------------------------------------
    def create_user(self, email, display_name, password_hash, role) -> str:
        uid = new_id("usr")
        self.ensure_user(uid, email, display_name, password_hash, role)
        return uid

    def ensure_user(self, user_id, email, display_name, password_hash, role) -> None:
        """Crée l'utilisateur à identifiant imposé s'il manque (idempotent)."""
        with self.engine.begin() as c:
            if c.execute(select(s.users.c.id).where(s.users.c.id == user_id)).first():
                return
            c.execute(insert(s.users).values(
                id=user_id, email=email, display_name=display_name,
                password_hash=password_hash, role=role))

    def get_user_by_email(self, email) -> dict | None:
        with self.engine.connect() as c:
            row = c.execute(select(s.users).where(s.users.c.email == email)).first()
        return dict(row._mapping) if row else None

    def create_dossier(self, name, client_name, language, owner_id) -> str:
        did = new_id("dos")
        with self.engine.begin() as c:
            c.execute(insert(s.dossiers).values(
                id=did, name=name, client_name=client_name, language=language, owner_id=owner_id))
            c.execute(insert(s.dossier_members).values(
                dossier_id=did, user_id=owner_id, role="consultant"))
        return did

    def get_dossier(self, dossier_id) -> dict | None:
        with self.engine.connect() as c:
            row = c.execute(select(s.dossiers).where(s.dossiers.c.id == dossier_id)).first()
        return dict(row._mapping) if row else None

    def list_dossiers(self, user_id) -> list[dict]:
        stmt = (select(s.dossiers).join(
            s.dossier_members, s.dossier_members.c.dossier_id == s.dossiers.c.id)
            .where(s.dossier_members.c.user_id == user_id).order_by(s.dossiers.c.created_at,
                                                                      s.dossiers.c.id))
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(stmt)]

    def add_member(self, dossier_id, user_id, role) -> None:
        with self.engine.begin() as c:
            exists = c.execute(select(s.dossier_members.c.role).where(
                s.dossier_members.c.dossier_id == dossier_id,
                s.dossier_members.c.user_id == user_id)).first()
            if exists:
                c.execute(update(s.dossier_members).where(
                    s.dossier_members.c.dossier_id == dossier_id,
                    s.dossier_members.c.user_id == user_id).values(role=role))
            else:
                c.execute(insert(s.dossier_members).values(
                    dossier_id=dossier_id, user_id=user_id, role=role))

    def member_role(self, dossier_id, user_id):
        with self.engine.connect() as c:
            return c.execute(select(s.dossier_members.c.role).where(
                s.dossier_members.c.dossier_id == dossier_id,
                s.dossier_members.c.user_id == user_id)).scalar()

    # --- documents et passages ----------------------------------------------------------------
    def add_document(self, dossier_id, parsed: ParsedDocument, stored_path,
                     role: str = "other") -> str:
        pages = max((b.page for b in parsed.blocks if b.page is not None), default=None)
        doc_id = new_id("doc")
        try:
            with self.engine.begin() as c:
                c.execute(insert(s.documents).values(
                    id=doc_id, dossier_id=dossier_id, filename=parsed.filename, mime=parsed.mime,
                    sha256=parsed.sha256, title=parsed.title, language=parsed.language,
                    pages=pages, stored_path=stored_path, role=role))
        except IntegrityError as exc:
            if self.find_document_by_sha(dossier_id, parsed.sha256):
                raise DuplicateDocumentError(parsed.sha256) from exc
            raise
        return doc_id

    def set_document_role(self, document_id, role) -> None:
        with self.engine.begin() as c:
            c.execute(update(s.documents).where(s.documents.c.id == document_id).values(role=role))

    def document_roles(self, dossier_id) -> dict[str, str]:
        """{document_id: rôle} pour tout le dossier, dans l'ordre d'import."""
        stmt = select(s.documents.c.id, s.documents.c.role).where(
            s.documents.c.dossier_id == dossier_id).order_by(s.documents.c.created_at,
                                                             s.documents.c.id)
        with self.engine.connect() as c:
            return {r[0]: r[1] for r in c.execute(stmt)}

    def find_document_by_sha(self, dossier_id, sha256) -> str | None:
        with self.engine.connect() as c:
            return c.execute(select(s.documents.c.id).where(
                s.documents.c.dossier_id == dossier_id, s.documents.c.sha256 == sha256)).scalar()

    def add_chunks(self, chunks, embeddings, model) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("autant de vecteurs que de passages")
        rows = [{
            "id": ch.id, "document_id": ch.document_id, "dossier_id": ch.dossier_id, "ordinal": ch.ordinal,
            "text": ch.text, "page_start": ch.page_start, "page_end": ch.page_end,
            "section_path": list(ch.section_path), "token_estimate": ch.token_estimate,
            "injection_flags": list(ch.injection_flags), "embedding": list(emb),
            "embedding_model": model} for ch, emb in zip(chunks, embeddings, strict=True)]
        if rows:
            with self.engine.begin() as c:
                c.execute(insert(s.chunks), rows)

    def get_chunks(self, dossier_id, chunk_ids) -> dict[str, Chunk]:
        if not chunk_ids:
            return {}
        stmt = select(s.chunks).where(
            s.chunks.c.dossier_id == dossier_id, s.chunks.c.id.in_(chunk_ids))
        with self.engine.connect() as c:
            return {r.id: _chunk(r) for r in c.execute(stmt)}

    def iter_chunks(self, dossier_id, document_ids=None) -> Iterator[Chunk]:
        stmt = select(s.chunks).where(s.chunks.c.dossier_id == dossier_id)
        if document_ids is not None:
            stmt = stmt.where(s.chunks.c.document_id.in_(document_ids))
        stmt = stmt.order_by(s.chunks.c.document_id, s.chunks.c.ordinal)
        with self.engine.connect() as c:
            for r in c.execute(stmt):
                yield _chunk(r)

    def vector_search(self, dossier_id, query, k, document_ids=None):
        return self._vectors.search(dossier_id, query, k, document_ids)

    # --- constats, livrables, versions, validation --------------------------------------------
    def save_findings(self, dossier_id, findings: list[Finding]) -> None:
        with self.engine.begin() as c:
            for f in findings:
                values = {"dossier_id": dossier_id, "text": f.text, "theme": f.theme,
                              "severity": f.severity, "source_ids": list(f.source_ids),
                              "validated": f.validated}
                known = c.execute(select(s.findings.c.dossier_id).where(
                    s.findings.c.id == f.id)).first()
                if known is None:
                    c.execute(insert(s.findings).values(id=f.id, **values))
                elif known[0] == dossier_id:
                    c.execute(update(s.findings).where(s.findings.c.id == f.id).values(**values))
                else:
                    raise ValueError("constat appartenant à un autre dossier")

    def list_findings(self, dossier_id, validated_only=False) -> list[Finding]:
        stmt = select(s.findings).where(s.findings.c.dossier_id == dossier_id)
        if validated_only:
            stmt = stmt.where(s.findings.c.validated.is_(True))
        with self.engine.connect() as c:
            return [Finding(id=r.id, dossier_id=r.dossier_id, text=r.text, theme=r.theme,
                            severity=r.severity, source_ids=list(r.source_ids),
                            validated=bool(r.validated)) for r in c.execute(stmt.order_by(s.findings.c.id))]

    def create_deliverable(self, dossier_id, type, template_id, author_id) -> str:
        did = new_id("dlv")
        with self.engine.begin() as c:
            c.execute(insert(s.deliverables).values(
                id=did, dossier_id=dossier_id, type=type, template_id=template_id,
                state="draft", current_version=0, author_id=author_id))
        return did

    def add_version(self, deliverable_id, content: DeliverableContent, author_id, origin) -> int:
        payload = content.model_dump(mode="json")
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.engine.begin() as c:
            last = c.execute(select(func.max(s.deliverable_versions.c.version)).where(
                s.deliverable_versions.c.deliverable_id == deliverable_id)).scalar() or 0
            version = last + 1
            c.execute(insert(s.deliverable_versions).values(
                deliverable_id=deliverable_id, version=version, content=payload, origin=origin,
                author_id=author_id, content_sha256=digest))
            c.execute(update(s.deliverables).where(s.deliverables.c.id == deliverable_id).values(
                current_version=version, updated_at=s.utcnow()))
        return version

    def get_version(self, deliverable_id, version=None):
        with self.engine.connect() as c:
            if version is None:
                version = c.execute(select(s.deliverables.c.current_version).where(
                    s.deliverables.c.id == deliverable_id)).scalar()
                if version is None:
                    raise KeyError(deliverable_id)
            row = c.execute(select(s.deliverable_versions.c.content).where(
                s.deliverable_versions.c.deliverable_id == deliverable_id,
                s.deliverable_versions.c.version == version)).first()
        if row is None:
            raise KeyError(f"{deliverable_id} v{version}")
        return version, DeliverableContent.model_validate(row[0])

    def set_state(self, deliverable_id, state, user_id, reason) -> None:
        with self.engine.begin() as c:
            row = c.execute(select(s.deliverables.c.state, s.deliverables.c.current_version).where(
                s.deliverables.c.id == deliverable_id)).first()
            if row is None:
                raise KeyError(deliverable_id)
            c.execute(insert(s.state_transitions).values(
                id=new_id("run"), deliverable_id=deliverable_id, version=row.current_version,
                from_state=row.state, to_state=state, user_id=user_id, reason=reason))
            c.execute(update(s.deliverables).where(s.deliverables.c.id == deliverable_id).values(
                state=state, updated_at=s.utcnow()))

    # --- traces -------------------------------------------------------------------------------
    def record_run(self, run: dict) -> str:
        values = {k: v for k, v in run.items() if k in _RUN_COLUMNS}
        values.setdefault("id", new_id("run"))
        values.setdefault("status", "ok")
        values.setdefault("attempts", 1)
        with self.engine.begin() as c:
            c.execute(insert(s.generation_runs).values(**values))
        return values["id"]

    def record_retrieval(self, run_id, passages: list[Passage]) -> None:
        rows = [{"run_id": run_id, "label": p.label, "chunk_id": p.chunk.id, "rank": i,
                     "score": p.score, "bm25_rank": p.ranks.get("bm25"),
                     "vector_rank": p.ranks.get("vector")} for i, p in enumerate(passages, 1)]
        if rows:
            with self.engine.begin() as c:
                c.execute(insert(s.retrieval_hits), rows)

    def record_verification(self, run_id, report: VerificationReport) -> None:
        rows = [{"run_id": run_id, "sentence_index": ck.index, "status": ck.status,
                     "numbers_cited": ck.numbers_cited, "numbers_found": ck.numbers_found,
                     "support": ck.support,
                     "issues": [i.model_dump(mode="json") for i in report.issues
                             if i.sentence_index == ck.index]} for ck in report.checks]
        if rows:
            with self.engine.begin() as c:
                c.execute(insert(s.verification_results), rows)

    def audit(self, user_id, action, object_type, object_id, details) -> None:
        """Ajout seul : aucune méthode ne modifie ni ne supprime une ligne du journal."""
        with self.engine.begin() as c:
            c.execute(insert(s.audit_log).values(
                user_id=user_id, action=action, object_type=object_type,
                object_id=object_id, details=details))

    def record_alert(self, chunk_id, codes) -> None:
        with self.engine.begin() as c:
            dossier_id = c.execute(select(s.chunks.c.dossier_id).where(
                s.chunks.c.id == chunk_id)).scalar()
            if dossier_id is None:
                raise KeyError(chunk_id)
            c.execute(insert(s.injection_alerts).values(
                id=new_id("chk"), chunk_id=chunk_id, dossier_id=dossier_id, codes=list(codes)))

    # --- priorités institutionnelles ----------------------------------------------------------
    def create_priority(self, dossier_id, *, title, description, rank, status, source_ids,
                        author_id) -> Priority:
        pid = new_id("prt")
        with self.engine.begin() as c:
            c.execute(insert(s.priorities).values(
                id=pid, dossier_id=dossier_id, title=title, description=description, rank=rank,
                status=status, source_ids=list(source_ids), author_id=author_id))
        return self.get_priority(pid)

    def get_priority(self, priority_id) -> Priority | None:
        with self.engine.connect() as c:
            row = c.execute(select(s.priorities).where(s.priorities.c.id == priority_id)).first()
        return _priority(row) if row else None

    def list_priorities(self, dossier_id, status: str | None = None) -> list[Priority]:
        stmt = select(s.priorities).where(s.priorities.c.dossier_id == dossier_id)
        if status is not None:
            stmt = stmt.where(s.priorities.c.status == status)
        with self.engine.connect() as c:
            return [_priority(r) for r in c.execute(
                stmt.order_by(s.priorities.c.rank, s.priorities.c.created_at, s.priorities.c.id))]

    def update_priority(self, priority_id, **values) -> Priority | None:
        with self.engine.begin() as c:
            c.execute(update(s.priorities).where(s.priorities.c.id == priority_id).values(
                updated_at=s.utcnow(), **values))
        return self.get_priority(priority_id)

    def delete_priority(self, priority_id) -> None:
        with self.engine.begin() as c:
            c.execute(delete(s.priorities).where(s.priorities.c.id == priority_id))

    # --- projets existants --------------------------------------------------------------------
    def create_project(self, dossier_id, *, title, state, duration_weeks, depends_on, source_ids,
                       author_id) -> ExistingProject:
        pid = new_id("prj")
        with self.engine.begin() as c:
            c.execute(insert(s.existing_projects).values(
                id=pid, dossier_id=dossier_id, title=title, state=state,
                duration_weeks=duration_weeks, depends_on=list(depends_on),
                source_ids=list(source_ids), author_id=author_id))
        return self.get_project(pid)

    def get_project(self, project_id) -> ExistingProject | None:
        with self.engine.connect() as c:
            row = c.execute(select(s.existing_projects).where(
                s.existing_projects.c.id == project_id)).first()
        return _project(row) if row else None

    def list_projects(self, dossier_id) -> list[ExistingProject]:
        stmt = select(s.existing_projects).where(s.existing_projects.c.dossier_id == dossier_id)
        with self.engine.connect() as c:
            return [_project(r) for r in c.execute(
                stmt.order_by(s.existing_projects.c.created_at, s.existing_projects.c.id))]

    def update_project(self, project_id, **values) -> ExistingProject | None:
        with self.engine.begin() as c:
            c.execute(update(s.existing_projects).where(
                s.existing_projects.c.id == project_id).values(updated_at=s.utcnow(), **values))
        return self.get_project(project_id)

    def delete_project(self, project_id) -> None:
        """Retire le projet et les dépendances d'autres projets vers lui."""
        with self.engine.begin() as c:
            rows = c.execute(select(s.existing_projects.c.id, s.existing_projects.c.depends_on)
                             ).all()
            for rid, deps in rows:
                if project_id in (deps or []):
                    c.execute(update(s.existing_projects).where(
                        s.existing_projects.c.id == rid).values(
                        depends_on=[d for d in deps if d != project_id]))
            c.execute(delete(s.existing_projects).where(s.existing_projects.c.id == project_id))
