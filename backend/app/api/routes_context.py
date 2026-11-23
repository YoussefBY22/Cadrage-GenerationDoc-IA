"""Fiche de contexte (FR-25) et chat de contexte : le chat propose, l'utilisateur confirme ailleurs."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.routes_dossiers import not_found
from app.domain.context import ProjectType
from app.services import Provider, Repo, User, chat, context_sheet, error_response
from app.services.generation import GenerationError
from app.services.search import SearchService, get_search_service

Search = Annotated[SearchService, Depends(get_search_service)]
router = APIRouter(tags=["context"])


class ContextPatch(BaseModel):
    sector: str | None = Field(default=None, max_length=200)
    size: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=50)
    project_types: list[ProjectType] | None = None
    scope: str | None = Field(default=None, max_length=2000)
    constraints: str | None = Field(default=None, max_length=2000)
    stakeholders: str | None = Field(default=None, max_length=2000)
    confirm: bool = False


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=chat.MAX_MESSAGE_CHARS)
    # L'historique est tenu par le navigateur : le serveur ne le stocke pas et ne le cite jamais.
    history: list[chat.HistoryTurn] = Field(default_factory=list, max_length=40)


def _member(repo, dossier_id, user) -> bool:
    return repo.member_role(dossier_id, user.id) is not None


def _dump(sheet, repo) -> dict:
    from app.services import coeur

    out = {"dossier_id": sheet.dossier_id, "data": sheet.data.model_dump(mode="json"),
           "confirmed": sheet.confirmed,
           "confirmed_at": sheet.confirmed_at.isoformat() if sheet.confirmed_at else None,
           "missing": sheet.data.missing(), "flags": context_sheet.flags(sheet.data)}
    nm = coeur.names(repo, [sheet.confirmed_by])
    out["confirmed_by_name"] = nm.get(sheet.confirmed_by or "")
    return out


@router.get("/dossiers/{dossier_id}/context")
def get_context(dossier_id: str, repo: Repo, user: User):
    if not _member(repo, dossier_id, user):
        return not_found("Dossier")
    return _dump(context_sheet.get(repo, dossier_id), repo)


@router.put("/dossiers/{dossier_id}/context")
def put_context(dossier_id: str, body: ContextPatch, repo: Repo, user: User):
    """Enregistre les champs envoyés ; `confirm: true` confirme la fiche (sinon : brouillon)."""
    if not _member(repo, dossier_id, user):
        return not_found("Dossier")
    changes = body.model_dump(exclude_unset=True, exclude={"confirm"})
    sheet = context_sheet.save(repo, dossier_id, user, changes, confirm=body.confirm)
    return _dump(sheet, repo)


@router.post("/dossiers/{dossier_id}/chat")
def ask_chat(dossier_id: str, body: ChatBody, repo: Repo, provider: Provider, user: User,
             search: Search):
    """Réponse courte et propositions. Aucune écriture : la confirmation passe par PUT /context
    et POST /decisions, appelés par l'utilisateur."""
    if not _member(repo, dossier_id, user):
        return not_found("Dossier")
    try:
        return chat.ask(repo, provider, search, dossier_id, user, body.message, body.history)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)
