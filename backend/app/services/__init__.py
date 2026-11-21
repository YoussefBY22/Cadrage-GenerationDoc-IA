"""Services métier (ingestion, recherche) appelés par les routes."""

from typing import Annotated

from fastapi import Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user, get_provider, get_repo
from app.domain.workflow import CurrentUser

# Alias de dépendances (évite Depends(...) dans les valeurs par défaut)
Repo = Annotated[object, Depends(get_repo)]
Provider = Annotated[object, Depends(get_provider)]
User = Annotated[CurrentUser, Depends(get_current_user)]


def error_response(status: int, code: str, message: str) -> JSONResponse:
    """Erreur au format de 06 §6 : {"error": {"code", "message"}}."""
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})
