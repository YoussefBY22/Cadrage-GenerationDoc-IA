"""Décisions humaines (FR-23) : budget, profil, calendrier… Seules les confirmées comptent."""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.api.routes_dossiers import not_found
from app.domain.decisions import DecisionCategory
from app.services import Repo, User, coeur, decisions, error_response
from app.services.generation import GenerationError

router = APIRouter(tags=["decisions"])


class DecisionBody(BaseModel):
    category: DecisionCategory
    text: str = Field(min_length=1, max_length=4000)
    status: Literal["proposed", "confirmed"] = "proposed"


class DecisionPatch(BaseModel):
    category: DecisionCategory | None = None
    text: str | None = Field(default=None, min_length=1, max_length=4000)


def _member(repo, dossier_id, user) -> bool:
    return repo.member_role(dossier_id, user.id) is not None


def _dump(d, repo) -> dict:
    out = d.model_dump(mode="json")
    nm = coeur.names(repo, [d.author_id, d.confirmed_by])
    out["author_name"] = nm.get(d.author_id or "")
    out["confirmed_by_name"] = nm.get(d.confirmed_by or "")
    return out


@router.get("/dossiers/{dossier_id}/decisions")
def list_decisions(dossier_id: str, repo: Repo, user: User):
    if not _member(repo, dossier_id, user):
        return not_found("Dossier")
    return [_dump(d, repo) for d in repo.list_decisions(dossier_id)]


@router.post("/dossiers/{dossier_id}/decisions", status_code=201)
def create_decision(dossier_id: str, body: DecisionBody, repo: Repo, user: User):
    if not _member(repo, dossier_id, user):
        return not_found("Dossier")
    try:
        return _dump(decisions.create(repo, dossier_id, user, **body.model_dump()), repo)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)


def _own(repo, decision_id, user):
    d = repo.get_decision(decision_id)
    return d if d is not None and _member(repo, d.dossier_id, user) else None


@router.patch("/decisions/{decision_id}")
def patch_decision(decision_id: str, body: DecisionPatch, repo: Repo, user: User):
    d = _own(repo, decision_id, user)
    if d is None:
        return not_found("Décision")
    try:
        return _dump(decisions.patch(repo, d, user, body.model_dump(exclude_unset=True)), repo)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)


@router.post("/decisions/{decision_id}:confirm")
def confirm_decision(decision_id: str, repo: Repo, user: User):
    d = _own(repo, decision_id, user)
    if d is None:
        return not_found("Décision")
    return _dump(decisions.confirm(repo, d, user), repo)


@router.post("/decisions/{decision_id}:retract")
def retract_decision(decision_id: str, repo: Repo, user: User):
    d = _own(repo, decision_id, user)
    if d is None:
        return not_found("Décision")
    return _dump(decisions.retract(repo, d, user), repo)


@router.delete("/decisions/{decision_id}", status_code=204)
def delete_decision(decision_id: str, repo: Repo, user: User):
    d = _own(repo, decision_id, user)
    if d is None:
        return not_found("Décision")
    repo.delete_decision(decision_id)
    repo.audit(user.id, "decision.delete", "decision", decision_id, {})
    return Response(status_code=204)
