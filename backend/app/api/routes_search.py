"""Recherche mixte dans un dossier."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.routes_dossiers import not_found
from app.services import Repo, User
from app.services.search import SearchService, get_search_service

Service = Annotated[SearchService, Depends(get_search_service)]
router = APIRouter(tags=["search"])


class SearchBody(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=10)
    k: int = Field(default=10, ge=1, le=50)
    document_ids: list[str] | None = None


@router.post("/dossiers/{dossier_id}/search")
def search(dossier_id: str, body: SearchBody, repo: Repo,
           user: User,
           service: Service):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    passages = service.search(dossier_id, body.texts, body.k, body.document_ids)
    return [p.model_dump(mode="json") for p in passages]
