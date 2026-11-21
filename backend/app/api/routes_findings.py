"""Constats : extraction, lecture, validation/correction par le consultant."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.routes_dossiers import not_found
from app.services import Provider, Repo, User, error_response, findings
from app.services.generation import GenerationError

router = APIRouter(tags=["findings"])


class FindingPatch(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    validated: bool | None = None


@router.post("/dossiers/{dossier_id}/findings:extract")
def extract_findings(dossier_id: str, repo: Repo, provider: Provider, user: User):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    return findings.extract(repo, provider, dossier_id, user)


@router.get("/dossiers/{dossier_id}/findings")
def list_findings(dossier_id: str, repo: Repo, user: User, validated_only: bool = False):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    return [f.model_dump(mode="json") for f in repo.list_findings(dossier_id, validated_only)]


@router.patch("/findings/{finding_id}")
def patch_finding(finding_id: str, body: FindingPatch, repo: Repo, user: User):
    f = findings.get_finding(repo, finding_id)
    if f is None or repo.member_role(f.dossier_id, user.id) is None:
        return not_found("Constat")
    try:
        return findings.patch_finding(repo, f, user, text=body.text, validated=body.validated)
    except GenerationError as exc:
        return error_response(exc.status, exc.code, exc.message)
