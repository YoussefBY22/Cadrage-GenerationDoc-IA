"""Cœur métier : priorités institutionnelles, projets existants, cohérence de la feuille de route."""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.api.routes_dossiers import not_found
from app.services import Repo, User, coeur, error_response, roadmap_service
from app.services.generation import GenerationError, get_deliverable

router = APIRouter(tags=["coeur"])

Status = Literal["proposed", "validated", "rejected"]
State = Literal["existing", "in_progress", "planned", "done"]


class PriorityBody(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=4000)
    rank: int | None = Field(default=None, ge=1, le=10000)
    status: Status = "proposed"
    source_ids: list[str] = []


class PriorityPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=4000)
    rank: int | None = Field(default=None, ge=1, le=10000)
    status: Status | None = None
    source_ids: list[str] | None = None


class ProjectBody(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    state: State = "existing"
    duration_weeks: int | None = Field(default=None, ge=1, le=520)
    depends_on: list[str] = []
    source_ids: list[str] = []


class ProjectPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    state: State | None = None
    duration_weeks: int | None = Field(default=None, ge=1, le=520)
    depends_on: list[str] | None = None
    source_ids: list[str] | None = None


def _member(repo, dossier_id, user) -> bool:
    return repo.member_role(dossier_id, user.id) is not None


def _dump(x, repo=None) -> dict:
    d = x.model_dump(mode="json")
    if repo is not None:
        nm = coeur.names(repo, [d.get("author_id"), d.get("validated_by")])
        d["author_name"] = nm.get(d.get("author_id") or "")
        d["validated_by_name"] = nm.get(d.get("validated_by") or "")
    return d


# --- priorités -----------------------------------------------------------------------------------
@router.get("/dossiers/{dossier_id}/priorities")
def list_priorities(dossier_id: str, repo: Repo, user: User):
    if not _member(repo, dossier_id, user):
        return not_found("Dossier")
    return [_dump(p, repo) for p in repo.list_priorities(dossier_id)]


@router.post("/dossiers/{dossier_id}/priorities", status_code=201)
def create_priority(dossier_id: str, body: PriorityBody, repo: Repo, user: User):
    if not _member(repo, dossier_id, user):
        return not_found("Dossier")
    try:
        return _dump(coeur.create_priority(repo, dossier_id, user, **body.model_dump()), repo)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)


@router.patch("/priorities/{priority_id}")
def patch_priority(priority_id: str, body: PriorityPatch, repo: Repo, user: User):
    p = repo.get_priority(priority_id)
    if p is None or not _member(repo, p.dossier_id, user):
        return not_found("Priorité")
    try:
        return _dump(coeur.patch_priority(repo, p, user, body.model_dump(exclude_unset=True)), repo)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)


@router.post("/priorities/{priority_id}:validate")
def validate_priority(priority_id: str, repo: Repo, user: User):
    return _decide(priority_id, "validated", repo, user)


@router.post("/priorities/{priority_id}:reject")
def reject_priority(priority_id: str, repo: Repo, user: User):
    return _decide(priority_id, "rejected", repo, user)


def _decide(priority_id: str, status: str, repo, user):
    p = repo.get_priority(priority_id)
    if p is None or not _member(repo, p.dossier_id, user):
        return not_found("Priorité")
    try:
        return _dump(coeur.decide(repo, p, user, status), repo)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)


@router.delete("/priorities/{priority_id}", status_code=204)
def delete_priority(priority_id: str, repo: Repo, user: User):
    p = repo.get_priority(priority_id)
    if p is None or not _member(repo, p.dossier_id, user):
        return not_found("Priorité")
    repo.delete_priority(priority_id)
    repo.audit(user.id, "priority.delete", "priority", priority_id, {})
    return Response(status_code=204)


# --- projets existants ---------------------------------------------------------------------------
@router.get("/dossiers/{dossier_id}/projects")
def list_projects(dossier_id: str, repo: Repo, user: User):
    if not _member(repo, dossier_id, user):
        return not_found("Dossier")
    return [_dump(p, repo) for p in repo.list_projects(dossier_id)]


@router.post("/dossiers/{dossier_id}/projects", status_code=201)
def create_project(dossier_id: str, body: ProjectBody, repo: Repo, user: User):
    if not _member(repo, dossier_id, user):
        return not_found("Dossier")
    try:
        return _dump(coeur.create_project(repo, dossier_id, user, **body.model_dump()), repo)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)


@router.patch("/projects/{project_id}")
def patch_project(project_id: str, body: ProjectPatch, repo: Repo, user: User):
    p = repo.get_project(project_id)
    if p is None or not _member(repo, p.dossier_id, user):
        return not_found("Projet")
    try:
        return _dump(coeur.patch_project(repo, p, user, body.model_dump(exclude_unset=True)), repo)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, repo: Repo, user: User):
    p = repo.get_project(project_id)
    if p is None or not _member(repo, p.dossier_id, user):
        return not_found("Projet")
    repo.delete_project(project_id)
    repo.audit(user.id, "project.delete", "project", project_id, {})
    return Response(status_code=204)


# --- cohérence -----------------------------------------------------------------------------------
@router.get("/deliverables/{deliverable_id}/coherence")
def get_coherence(deliverable_id: str, repo: Repo, user: User):
    row = get_deliverable(repo, deliverable_id)
    if row is None or not _member(repo, row["dossier_id"], user):
        return not_found("Livrable")
    try:
        return roadmap_service.coherence(repo, deliverable_id)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)
