"""Transitions d'état d'un livrable et acquittement des phrases en échec."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.routes_deliverables import load_deliverable
from app.config import get_settings
from app.generation.template_loader import TemplateError, template_for
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
    reason: str | None = None  # motif, obligatoire


def _not_found():
    return error_response(404, "NOT_FOUND", "Livrable introuvable")


def _approval_facts(repo, d, version, content) -> tuple[int, bool, int]:
    """(phrases en échec non acquittées, toutes les sections présentes, initiatives non fondées)."""
    acked = vs.acknowledgements(repo, d["id"], version)
    _, hard, soft = vs.evidence_status(repo, d["dossier_id"], content,
                                       get_settings().support_threshold)
    failures = len(hard) + len(soft - acked)  # un défaut de preuve ne s'acquitte jamais
    by_key = {sec.section_key: sec for sec in content.sections}
    try:
        required = [x.key for x in template_for(content).sections]
    except TemplateError:
        return failures, False, len(vs.initiative_issues(repo, d["dossier_id"], content))
    complete = all(
        k in by_key and ((by_key[k].status == "ok" and by_key[k].sentences) or (k, -1) in acked)
        for k in required)
    return failures, complete, len(vs.initiative_issues(repo, d["dossier_id"], content))


@router.post("/deliverables/{deliverable_id}/transitions")
def transition(deliverable_id: str, body: TransitionIn, repo: Repo, user: User):
    d = load_deliverable(repo, deliverable_id, user)
    if d is None:
        return _not_found()
    if body.to not in ("draft", "in_review", "approved", "rejected"):
        return error_response(422, "INVALID_STATE", "État inconnu")
    version, content = repo.get_version(deliverable_id)
    member = repo.member_role(d["dossier_id"], user.id)
    failures, complete, unverified = (0, True, 0)
    if body.to == "approved":
        failures, complete, unverified = _approval_facts(repo, d, version, content)
    ctx = TransitionContext(
        current=d["state"], to=body.to, reason=body.reason, actor_id=user.id,
        actor_can_review=member in ("reviewer", "admin") or user.role == "admin",
        version_author_id=vs.version_author(repo, deliverable_id, version) or d["author_id"],
        deliverable_author_id=d["author_id"],
        allow_self_approval=get_settings().allow_self_approval,
        unacknowledged_failures=failures, sections_complete=complete,
        unverified_initiatives=unverified)
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
    version, content = repo.get_version(deliverable_id)
    if not (body.reason or "").strip():
        return error_response(422, "REASON_REQUIRED", "Un motif est obligatoire pour acquitter")
    authors = {d["author_id"], vs.version_author(repo, deliverable_id, version)}
    if user.id in authors and not get_settings().allow_self_approval:
        return error_response(409, "FOUR_EYES", "L'auteur ne peut pas acquitter son propre livrable")
    _, hard, _ = vs.evidence_status(repo, d["dossier_id"], content, get_settings().support_threshold)
    if (body.section_key, body.sentence_index) in hard:
        return error_response(409, "NOT_ACKNOWLEDGEABLE",
                              "Défaut de preuve : à corriger, pas à acquitter")
    repo.audit(user.id, "sentence.acknowledge", "deliverable", deliverable_id,
               {"version": version, "section_key": body.section_key,
                "sentence_index": body.sentence_index, "reason": body.reason.strip()})
    return {"version": version, "section_key": body.section_key,
            "sentence_index": body.sentence_index}
