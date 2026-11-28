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
    mode: str = Field(default="meaning", pattern="^(meaning|words)$")  # words : mots exacts, instantané


@router.post("/dossiers/{dossier_id}/search")
def search(dossier_id: str, body: SearchBody, repo: Repo,
           user: User,
           service: Service):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    import time
    start = time.perf_counter()
    passages = service.search(dossier_id, body.texts, body.k, body.document_ids, lexical_only=body.mode == "words")
    ms = int((time.perf_counter() - start) * 1000)
    from app.services.ingestion import get_document
    names: dict = {}
    out = []
    for p in passages:
        d = p.chunk.document_id
        if d not in names:
            names[d] = (get_document(repo, d) or {}).get("filename", d)
        out.append({**p.model_dump(mode="json"), "filename": names[d], "elapsed_ms": ms})
    return out
