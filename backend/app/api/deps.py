"""Dépendances FastAPI communes (fournisseur de modèle, dépôt, utilisateur courant)."""

from fastapi import HTTPException, Request

from ..config import get_settings
from ..domain.workflow import CurrentUser


def get_provider(request: Request):
    return request.app.state.provider


def get_repo(request: Request):
    """Dépôt de données ; construit au premier besoin s'il n'a pas été fourni."""
    state = request.app.state
    if getattr(state, "repo", None) is None:
        from ..storage import build_repository

        state.repo = build_repository(get_settings())
    return state.repo


def get_current_user(request: Request) -> CurrentUser:
    """Mode « dev » : administrateur local. Mode « token » : implémenté par D1."""
    if get_settings().auth_mode == "dev":
        return CurrentUser(id="usr_dev", role="admin")
    raise HTTPException(status_code=401, detail="Authentification requise")
