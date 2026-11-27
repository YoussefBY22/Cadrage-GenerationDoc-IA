"""Dossiers : création et lecture, réservées aux membres (404 pour les autres)."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.services import Repo, User, error_response, suppression

router = APIRouter(tags=["dossiers"])


class DossierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    client_name: str = Field(min_length=1, max_length=255)
    language: Literal["fr", "en"] = "fr"


def not_found(what: str = "Objet"):
    return error_response(404, "NOT_FOUND", f"{what} introuvable")


def _view(d: dict) -> dict:
    created = d.get("created_at")
    return {"id": d["id"], "name": d["name"], "client_name": d["client_name"],
            "language": d["language"], "created_at": created.isoformat() if created else None}


@router.post("/dossiers", status_code=201)
def create_dossier(body: DossierCreate, repo: Repo,
                   user: User):
    did = repo.create_dossier(body.name, body.client_name, body.language, user.id)
    repo.add_member(did, user.id, "consultant")  # le créateur est membre (idempotent)
    repo.audit(user.id, "dossier.create", "dossier", did, {})
    return _view(repo.get_dossier(did))


@router.get("/dossiers")
def list_dossiers(repo: Repo, user: User):
    return [_view(d) for d in repo.list_dossiers(user.id)]


@router.get("/dossiers/{dossier_id}")
def get_dossier(dossier_id: str, repo: Repo,
                user: User):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    return _view(repo.get_dossier(dossier_id))


@router.get("/dossiers/{dossier_id}/delete-preview")
def dossier_delete_preview(dossier_id: str, repo: Repo, user: User):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    return suppression.dossier_counts(repo.engine, dossier_id)


@router.delete("/dossiers/{dossier_id}")
def delete_dossier(dossier_id: str, request: Request, repo: Repo, user: User):
    """Supprime le dossier et tout son contenu (documents, constats, livrables...). Irréversible."""
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    out = suppression.delete_dossier(repo.engine, dossier_id)
    from app.services.search import get_search_service
    get_search_service(request).invalidate(dossier_id)
    repo.audit(user.id, "dossier.delete", "dossier", dossier_id, out)
    return out
