"""Génération : feuille de route, création de livrables (ToR, CdC), génération de sections."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.routes_dossiers import not_found
from app.domain.context import ProjectType
from app.domain.roadmap import Criterion
from app.services import Provider, Repo, User, error_response, generation, roadmap_service
from app.services.generation import GenerationError, get_deliverable
from app.services.search import SearchService, get_search_service

Search = Annotated[SearchService, Depends(get_search_service)]
router = APIRouter(tags=["generation"])


class RoadmapBody(BaseModel):
    language: Literal["fr", "en"] | None = None  # défaut : langue du dossier
    criteria: list[Criterion] | None = None
    waves: int = Field(default=3, ge=1, le=6)


class ScorePatch(BaseModel):
    key: str
    value: int = Field(ge=1, le=5)
    rationale: str | None = None


class InitiativePatch(BaseModel):
    id: str
    scores: list[ScorePatch] | None = None
    duration_weeks: int | None = Field(default=None, ge=1, le=520)
    depends_on: list[str] | None = None
    objective: str | None = Field(default=None, max_length=2000)
    expected_result: str | None = Field(default=None, max_length=2000)
    indicator: str | None = Field(default=None, max_length=2000)
    priority_ids: list[str] | None = None
    accept_proposal: bool | None = None
    depends_on_projects: list[str] | None = None


class RoadmapPatch(BaseModel):
    initiatives: list[InitiativePatch] = Field(min_length=1)
    waves: int | None = Field(default=None, ge=1, le=6)


class DeliverableBody(BaseModel):
    type: Literal["tor", "cdc", "roadmap", "findings"]
    template_id: str | None = None
    initiative_id: str | None = None
    language: Literal["fr", "en"] | None = None  # défaut : langue du dossier
    # modules par type de projet ; absent = types de la fiche confirmée ; [] = tronc commun seul
    modules: list[ProjectType] | None = None


def _member(repo, dossier_id, user) -> bool:
    return repo.member_role(dossier_id, user.id) is not None


def _own(repo, deliverable_id, user):
    row = get_deliverable(repo, deliverable_id)
    return row if row and _member(repo, row["dossier_id"], user) else None


@router.post("/dossiers/{dossier_id}/roadmap:generate")
def generate_roadmap(dossier_id: str, body: RoadmapBody, repo: Repo, provider: Provider, user: User):
    if not _member(repo, dossier_id, user):
        return not_found("Dossier")
    try:
        return roadmap_service.generate(
            repo, provider, dossier_id, user, criteria=body.criteria, waves=body.waves,
            language=body.language or repo.get_dossier(dossier_id)["language"])
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)


@router.patch("/deliverables/{deliverable_id}/roadmap")
def patch_roadmap(deliverable_id: str, body: RoadmapPatch, repo: Repo, user: User):
    if _own(repo, deliverable_id, user) is None:
        return not_found("Livrable")
    try:
        return roadmap_service.patch(
            repo, deliverable_id, user, [c.model_dump(exclude_unset=True) for c in body.initiatives],
            waves=body.waves)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)


@router.post("/dossiers/{dossier_id}/deliverables", status_code=201)
def create_deliverable(dossier_id: str, body: DeliverableBody, repo: Repo, user: User):
    if not _member(repo, dossier_id, user):
        return not_found("Dossier")
    try:
        did = generation.create_deliverable(
            repo, dossier_id, body.type, user, initiative_id=body.initiative_id,
            language=body.language or repo.get_dossier(dossier_id)["language"],
            modules=body.modules)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)
    return {"deliverable_id": did, "type": body.type}


@router.post("/deliverables/{deliverable_id}/sections/{section_key}:generate")
def generate_section(deliverable_id: str, section_key: str, repo: Repo, provider: Provider,
                     user: User, search: Search, proposal: bool = False):
    """``?proposal=true`` : le consultant demande une proposition malgré l'absence de passage direct."""
    if _own(repo, deliverable_id, user) is None:
        return not_found("Livrable")
    try:
        if proposal:
            from app.config import get_settings
            from app.llm import build_proposal_provider
            provider = build_proposal_provider(get_settings(), provider)
        return generation.generate_section(repo, provider, search, deliverable_id, section_key, user,
                                           proposal=proposal)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)
