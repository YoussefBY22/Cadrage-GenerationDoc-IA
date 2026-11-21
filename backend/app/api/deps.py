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


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def get_current_user(request: Request) -> CurrentUser:
    """Mode « dev » : administrateur local. Mode « token » : jeton porteur de session."""
    if get_settings().auth_mode == "dev":
        return CurrentUser(id="usr_dev", role="admin")
    from ..auth.tokens import user_for_token

    token = bearer_token(request)
    user = user_for_token(get_repo(request).engine, token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Authentification requise",
                            headers={"WWW-Authenticate": "Bearer"})
    return CurrentUser(id=user["id"], role=user["role"])
