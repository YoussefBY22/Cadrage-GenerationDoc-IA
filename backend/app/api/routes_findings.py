"""Constats : extraction, lecture, validation/correction par le consultant."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.routes_dossiers import not_found
from app.services import Provider, Repo, User, error_response, findings
from app.services.generation import GenerationError

router = APIRouter(tags=["findings"])


class FindingPatch(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    validated: bool | None = None


@router.post("/dossiers/{dossier_id}/findings:extract")
def extract_findings(dossier_id: str, repo: Repo, provider: Provider, user: User):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    return findings.extract(repo, provider, dossier_id, user)


@router.get("/dossiers/{dossier_id}/findings")
def list_findings(dossier_id: str, repo: Repo, user: User, validated_only: bool = False):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    items = repo.list_findings(dossier_id, validated_only)
    refs = source_refs(repo, dossier_id)
    return [{**f.model_dump(mode="json"), "sources": [refs[x] for x in f.source_ids if x in refs]}
            for f in items]


def source_refs(repo, dossier_id: str) -> dict:
    """Passage -> document, page, rang : pour afficher « document | page » et trier dans l'ordre du document."""
    from sqlalchemy import select

    from app.storage import schema as s
    with repo.engine.connect() as c:
        rows = c.execute(select(s.chunks.c.id, s.chunks.c.document_id, s.chunks.c.page_start, s.chunks.c.page_end,
                                s.chunks.c.ordinal, s.documents.c.filename, s.documents.c.created_at)
                         .join(s.documents, s.documents.c.id == s.chunks.c.document_id)
                         .where(s.chunks.c.dossier_id == dossier_id)).all()
    docs = sorted({(r.created_at, r.document_id) for r in rows}, key=lambda x: (str(x[0]), x[1]))
    rank = {d: i for i, (_, d) in enumerate(docs)}
    return {r.id: {"chunk_id": r.id, "document_id": r.document_id, "filename": r.filename,
                   "page_start": r.page_start, "page_end": r.page_end, "ordinal": r.ordinal,
                   "document_rank": rank[r.document_id]} for r in rows}


@router.patch("/findings/{finding_id}")
def patch_finding(finding_id: str, body: FindingPatch, repo: Repo, user: User):
    f = findings.get_finding(repo, finding_id)
    if f is None or repo.member_role(f.dossier_id, user.id) is None:
        return not_found("Constat")
    try:
        return findings.patch_finding(repo, f, user, text=body.text, validated=body.validated)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)
