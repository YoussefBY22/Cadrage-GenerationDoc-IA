"""Transitions d'état d'un livrable et acquittement des phrases en échec."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.routes_deliverables import load_deliverable
from app.config import get_settings
from app.generation.template_loader import TemplateError, load_template
from app.services import Repo, User, error_response
from app.workflow import versions as vs
from app.workflow.state_machine import TransitionContext, WorkflowError, check_transition

router = APIRouter(tags=["workflow"])


class TransitionIn(BaseModel):
    to: str
    reason: str | None = None


class AckIn(BaseModel):
    section_key: str
    sentence_index: int = -1   # -1 : acquitte le refus (insufficient_evidence) de la section


def _not_found():
    return error_response(404, "NOT_FOUND", "Livrable introuvable")


def _approval_facts(repo, d, version, content) -> tuple[int, bool]:
    """(phrases en échec non acquittées, toutes les sections présentes)."""
    acked = vs.acknowledgements(repo, d["id"], version)
    reports = vs.verify_content(repo, d["dossier_id"], content, get_settings().support_threshold)
    failures = sum(1 for sec, r in zip(content.sections, reports, strict=True)
                   for ck in r.checks if ck.status == "failed"
                   and (sec.section_key, ck.index) not in acked)
    by_key = {sec.section_key: sec for sec in content.sections}
    try:
        required = [x.key for x in load_template(content.type, content.language).sections]
    except TemplateError:
        required = list(by_key)
    complete = bool(by_key) and all(
        k in by_key and (by_key[k].status == "ok" or (k, -1) in acked) for k in required)
    return failures, complete


@router.post("/deliverables/{deliverable_id}/transitions")
def transition(deliverable_id: str, body: TransitionIn, repo: Repo, user: User):
    d = load_deliverable(repo, deliverable_id, user)
    if d is None:
        return _not_found()
    if body.to not in ("draft", "in_review", "approved", "rejected"):
        return error_response(422, "INVALID_STATE", "État inconnu")
    version, content = repo.get_version(deliverable_id)
    member = repo.member_role(d["dossier_id"], user.id)
    failures, complete = (0, True)
    if body.to == "approved":
        failures, complete = _approval_facts(repo, d, version, content)
    ctx = TransitionContext(
        current=d["state"], to=body.to, reason=body.reason, actor_id=user.id,
        actor_can_review=member in ("reviewer", "admin") or user.role == "admin",
        version_author_id=vs.version_author(repo, deliverable_id, version) or d["author_id"],
        deliverable_author_id=d["author_id"],
        allow_self_approval=get_settings().allow_self_approval,
        unacknowledged_failures=failures, sections_complete=complete)
    try:
        check_transition(ctx)
    except WorkflowError as exc:
        return error_response(exc.status, exc.code, exc.message)
    repo.set_state(deliverable_id, body.to, user.id, body.reason)
    repo.audit(user.id, "transition", "deliverable", deliverable_id,
               {"from": d["state"], "to": body.to, "version": version, "reason": body.reason})
    return {"id": deliverable_id, "state": body.to, "version": version}


@router.post("/deliverables/{deliverable_id}/acknowledgements", status_code=201)
def acknowledge(deliverable_id: str, body: AckIn, repo: Repo, user: User):
    d = load_deliverable(repo, deliverable_id, user)
    if d is None:
        return _not_found()
    member = repo.member_role(d["dossier_id"], user.id)
    if member not in ("reviewer", "admin") and user.role != "admin":
        return error_response(403, "FORBIDDEN_ROLE", "Rôle relecteur ou admin requis")
    version, _ = repo.get_version(deliverable_id)
    repo.audit(user.id, "sentence.acknowledge", "deliverable", deliverable_id,
               {"version": version, "section_key": body.section_key,
                "sentence_index": body.sentence_index})
    return {"version": version, "section_key": body.section_key,
            "sentence_index": body.sentence_index}
