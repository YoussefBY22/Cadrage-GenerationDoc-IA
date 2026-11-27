"""Documents et passages : import (multipart), liste, détail. Objet d'un autre dossier -> 404."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.routes_dossiers import not_found
from app.services import Provider, Repo, User, error_response, ingestion, suppression
from app.services.search import get_search_service

router = APIRouter(tags=["documents"])


@router.post("/dossiers/{dossier_id}/documents", status_code=201)
async def upload_document(dossier_id: str, file: UploadFile, request: Request,
                          repo: Repo, provider: Provider,
                          user: User, role: Annotated[str, Form()] = "other"):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    data = await file.read()
    try:
        return ingestion.ingest(repo, provider, dossier_id, file.filename or "", data, user,
                                search=get_search_service(request), role=role)
    except ingestion.IngestionError as exc:
        return error_response(exc.status, exc.code, exc.message)


@router.get("/dossiers/{dossier_id}/documents")
def list_documents(dossier_id: str, repo: Repo,
                   user: User):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    return ingestion.list_documents(repo, dossier_id)


@router.get("/documents/{document_id}")
def get_document(document_id: str, repo: Repo,
                 user: User):
    doc = ingestion.get_document(repo, document_id)
    if doc is None or repo.member_role(doc["dossier_id"], user.id) is None:
        return not_found("Document")
    return doc


class RolePatch(BaseModel):
    role: str


@router.patch("/documents/{document_id}")
def patch_document(document_id: str, body: RolePatch, repo: Repo, user: User):
    """Change le rôle d'un document (diagnostic, strategy, portfolio, template, other)."""
    doc = ingestion.get_document(repo, document_id)
    if doc is None or repo.member_role(doc["dossier_id"], user.id) is None:
        return not_found("Document")
    try:
        ingestion.set_role(repo, document_id, body.role, user)
    except ingestion.IngestionError as exc:
        return error_response(exc.status, exc.code, exc.message)
    return ingestion.get_document(repo, document_id)


@router.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: str, repo: Repo,
              user: User):
    chunk = ingestion.get_chunk(repo, chunk_id)
    if chunk is None or repo.member_role(chunk["dossier_id"], user.id) is None:
        return not_found("Passage")
    return chunk


@router.get("/documents/{document_id}/file")
def document_file(document_id: str, repo: Repo, user: User):
    """Le fichier d'origine, affiché dans le navigateur (inline), jamais forcé en téléchargement."""
    doc = ingestion.get_document(repo, document_id)
    if doc is None or repo.member_role(doc["dossier_id"], user.id) is None:
        return not_found("Document")
    with repo.engine.connect() as c:
        from sqlalchemy import select

        from app.storage import schema as s
        row = c.execute(select(s.documents.c.stored_path, s.documents.c.mime, s.documents.c.filename)
                        .where(s.documents.c.id == document_id)).first()
    if not row or not row.stored_path or not Path(row.stored_path).is_file():
        return not_found("Fichier")
    return FileResponse(row.stored_path, media_type=row.mime or "application/pdf",
                        filename=row.filename, content_disposition_type="inline")


@router.get("/documents/{document_id}/delete-preview")
def document_delete_preview(document_id: str, repo: Repo, user: User):
    doc = ingestion.get_document(repo, document_id)
    if doc is None or repo.member_role(doc["dossier_id"], user.id) is None:
        return not_found("Document")
    return suppression.document_counts(repo.engine, document_id)


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, request: Request, repo: Repo, user: User):
    doc = ingestion.get_document(repo, document_id)
    if doc is None or repo.member_role(doc["dossier_id"], user.id) is None:
        return not_found("Document")
    out = suppression.delete_document(repo.engine, document_id)
    get_search_service(request).invalidate(doc["dossier_id"])
    repo.audit(user.id, "document.delete", "document", document_id,
               {k: v for k, v in out.items() if k != "dossier_id"})
    return out
