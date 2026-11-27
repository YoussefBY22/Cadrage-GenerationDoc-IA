"""Assistant de toutes les pages : état du dossier, aide de la page, questions sur les documents."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.routes_dossiers import not_found
from app.services import Provider, Repo, User, assistant
from app.services.search import get_search_service

router = APIRouter(tags=["assistant"])


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(max_length=2000)


class AssistantBody(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=12)
    page_help: str | None = Field(default=None, max_length=1500)


@router.post("/dossiers/{dossier_id}/assistant")
def ask(dossier_id: str, body: AssistantBody, request: Request, repo: Repo, provider: Provider, user: User):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    return assistant.ask(repo, provider, get_search_service(request), dossier_id, body.message,
                         [t.model_dump() for t in body.history], body.page_help, user.id)


@router.post("/assistant")
def ask_general(body: AssistantBody, user: User):
    """Hors dossier (tableau de bord) : aide de la page uniquement, sans modèle."""
    return {"answer": body.page_help or ("Ouvrez un dossier pour que je puisse répondre sur ses documents, "
                                         "constats et livrables."), "sources": [], "model": False, "busy": []}
