"""Livrables : lecture, versions, édition, restauration, différences, commentaires."""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.domain.generation import DeliverableContent
from app.services import Repo, User, error_response
from app.workflow import versions as vs
from app.workflow.diffing import diff_contents
from app.workflow.state_machine import can_edit

router = APIRouter(tags=["deliverables"])

NOT_FOUND = ("NOT_FOUND", "Livrable introuvable")


def load_deliverable(repo, deliverable_id: str, user) -> dict | None:
    """Livrable si l'utilisateur est membre de son dossier ; sinon None (=> 404, pas 403)."""
    d = vs.get_deliverable(repo, deliverable_id)
    if d is None or repo.member_role(d["dossier_id"], user.id) is None:
        return None
    return d


def _not_found():
    return error_response(404, *NOT_FOUND)


def _reports(repo, d, content):
    reports = vs.verify_content(repo, d["dossier_id"], content, get_settings().support_threshold)
    return [{"report": r.model_dump(mode="json"), "tpv": r.tpv} for r in reports]


def _editable_or_error(d):
    if not can_edit(d["state"]):
        return error_response(409, "NOT_EDITABLE",
                              f"Modification impossible à l'état {d['state']}")
    return None


def _after_edit(repo, d, user, version: int):
    """Un livrable approuvé modifié redevient brouillon (approbation perdue)."""
    if d["state"] == "approved":
        repo.set_state(d["id"], "draft", user.id, "modification après approbation")
        repo.audit(user.id, "transition", "deliverable", d["id"],
                   {"from": "approved", "to": "draft", "version": version, "auto": True})


@router.get("/deliverables/{deliverable_id}")
def get_deliverable(deliverable_id: str, repo: Repo, user: User):
    d = load_deliverable(repo, deliverable_id, user)
    if d is None:
        return _not_found()
    version, content = repo.get_version(deliverable_id)
    return {"id": d["id"], "dossier_id": d["dossier_id"], "type": d["type"], "state": d["state"],
            "template_id": d["template_id"], "version": version,
            "content": content.model_dump(mode="json"), "reports": _reports(repo, d, content),
            "initiative_issues": vs.initiative_issues(repo, d["dossier_id"], content)}


@router.get("/deliverables/{deliverable_id}/versions")
def list_versions(deliverable_id: str, repo: Repo, user: User):
    if load_deliverable(repo, deliverable_id, user) is None:
        return _not_found()
    return vs.list_versions(repo, deliverable_id)


@router.get("/deliverables/{deliverable_id}/versions/{n}")
def get_version(deliverable_id: str, n: int, repo: Repo, user: User):
    if load_deliverable(repo, deliverable_id, user) is None:
        return _not_found()
    try:
        _, content = repo.get_version(deliverable_id, n)
    except KeyError:
        return error_response(404, "NOT_FOUND", "Version introuvable")
    return {"version": n, "content": content.model_dump(mode="json")}


@router.put("/deliverables/{deliverable_id}/content")
def put_content(deliverable_id: str, body: dict, repo: Repo, user: User):
    d = load_deliverable(repo, deliverable_id, user)
    if d is None:
        return _not_found()
    if (err := _editable_or_error(d)) is not None:
        return err
    try:
        content = DeliverableContent.model_validate(body)
    except ValidationError as exc:
        return error_response(422, "INVALID_CONTENT", f"Contenu invalide : {exc.error_count()} erreur(s)")
    _, current = repo.get_version(deliverable_id)
    fields = ("type", "language", "template_id", "template_version")
    if any(getattr(content, f) != getattr(current, f) for f in fields) or content.type != d["type"]:
        return error_response(422, "IDENTITY_CHANGED",
                              "Type, langue et gabarit d'un livrable ne changent pas à l'édition")
    if content.type == "roadmap" and content.roadmap is None:
        return error_response(422, "ROADMAP_REQUIRED", "Une feuille de route garde ses initiatives")
    version = repo.add_version(deliverable_id, content, user.id, "edited")
    repo.audit(user.id, "content.edit", "deliverable", deliverable_id, {"version": version})
    _after_edit(repo, d, user, version)
    return {"version": version, "reports": _reports(repo, d, content)}


@router.post("/deliverables/{deliverable_id}/versions/{n:int}:restore")
def restore_version(deliverable_id: str, n: int, repo: Repo, user: User):
    d = load_deliverable(repo, deliverable_id, user)
    if d is None:
        return _not_found()
    if (err := _editable_or_error(d)) is not None:
        return err
    try:
        _, content = repo.get_version(deliverable_id, n)
    except KeyError:
        return error_response(404, "NOT_FOUND", "Version introuvable")
    version = repo.add_version(deliverable_id, content, user.id, "restored")
    repo.audit(user.id, "version.restore", "deliverable", deliverable_id,
               {"version": version, "restored_from": n})
    _after_edit(repo, d, user, version)
    return {"version": version, "restored_from": n, "reports": _reports(repo, d, content)}


@router.get("/deliverables/{deliverable_id}/diff")
def diff(deliverable_id: str, repo: Repo, user: User,
         from_: int = Query(alias="from"), to: int = Query()):
    if load_deliverable(repo, deliverable_id, user) is None:
        return _not_found()
    try:
        _, old = repo.get_version(deliverable_id, from_)
        _, new = repo.get_version(deliverable_id, to)
    except KeyError:
        return error_response(404, "NOT_FOUND", "Version introuvable")
    return {"from": from_, "to": to, "sections": diff_contents(old, new)}


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


@router.post("/deliverables/{deliverable_id}/sections/{key}/comments", status_code=201)
def add_comment(deliverable_id: str, key: str, body: CommentIn, repo: Repo, user: User):
    if load_deliverable(repo, deliverable_id, user) is None:
        return _not_found()
    cid = vs.add_comment(repo, deliverable_id, key, user.id, body.text)
    repo.audit(user.id, "comment.add", "deliverable", deliverable_id,
               {"section_key": key, "comment_id": cid})
    return {"id": cid, "section_key": key}


@router.get("/deliverables/{deliverable_id}/comments")
def list_comments(deliverable_id: str, repo: Repo, user: User):
    if load_deliverable(repo, deliverable_id, user) is None:
        return _not_found()
    return vs.list_comments(repo, deliverable_id)
