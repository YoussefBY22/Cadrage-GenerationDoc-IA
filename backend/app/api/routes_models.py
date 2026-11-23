"""Modèles de langage (administrateur) : lister, tester, activer, revenir en arrière.

Réponses documentées dans docs/api-modeles.md (types `ModelsOverview`, `TestReport`, `ContextBudget`).
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models_registry import RegistryError, RegistryService
from app.services import Repo, User, error_response

router = APIRouter(tags=["models"])


class ModelBody(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    role: str = "generation"   # « embedding » est toujours refusé : réindexation requise


def _service() -> RegistryService:
    return RegistryService(get_settings())


def _guard(user):
    if user.role != "admin":
        return error_response(403, "FORBIDDEN_ROLE", "Réservé aux administrateurs")
    return None


def _run(fn):
    try:
        return fn()
    except RegistryError as exc:
        return error_response(exc.status, exc.code, exc.message)


@router.get("/admin/models")
def list_models(user: User):
    return _guard(user) or _run(lambda: _service().list())


@router.get("/admin/models/context")
def context_budget(user: User, candidate_tokens: int | None = None):
    """Répartition de la fenêtre pour une section ; `candidate_tokens` simule la taille des passages retrouvés."""
    return _guard(user) or _run(lambda: _service().context(candidate_tokens))


@router.post("/admin/models/test")
def test_model(body: ModelBody, user: User):
    return _guard(user) or _run(lambda: _service().test(body.model))


@router.post("/admin/models/activate")
def activate_model(body: ModelBody, repo: Repo, user: User):
    def go():
        result = _service().activate(body.model, by=user.id, role=body.role)
        repo.audit(user.id, "model.activate", "model", body.model, {"previous": result["previous"]})
        return result
    return _guard(user) or _run(go)


@router.post("/admin/models/rollback")
def rollback_model(repo: Repo, user: User):
    def go():
        result = _service().rollback(by=user.id)
        repo.audit(user.id, "model.rollback", "model", result["active"],
                   {"previous": result["previous"]})
        return result
    return _guard(user) or _run(go)
