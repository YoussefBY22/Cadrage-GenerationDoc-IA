"""Journal d'audit (lecture seule) : relecteurs et administrateurs."""

from fastapi import APIRouter

from app.services import Repo, User, error_response
from app.workflow.versions import list_audit

router = APIRouter(tags=["audit"])


@router.get("/audit")
def get_audit(repo: Repo, user: User, object_id: str | None = None):
    if user.role not in ("reviewer", "admin"):
        return error_response(403, "FORBIDDEN_ROLE", "Réservé aux relecteurs et administrateurs")
    return list_audit(repo, object_id)
