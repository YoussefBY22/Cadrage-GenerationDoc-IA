"""Cœur métier : rôle des documents, priorités institutionnelles, projets existants."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DocumentRole = Literal["diagnostic", "strategy", "portfolio", "template", "other"]
DOCUMENT_ROLES: tuple[str, ...] = ("diagnostic", "strategy", "portfolio", "template", "other")
DEFAULT_ROLE = "other"

PriorityStatus = Literal["proposed", "validated", "rejected"]
ProjectState = Literal["existing", "in_progress", "planned", "done"]


class Priority(BaseModel):
    """Priorité institutionnelle : décision humaine, citable ; seule `validated` sert à générer."""

    model_config = ConfigDict(frozen=True)

    id: str
    dossier_id: str
    title: str
    description: str = ""
    rank: int
    status: PriorityStatus = "proposed"
    source_ids: list[str] = []
    author_id: str | None = None
    validated_by: str | None = None
    validated_at: datetime | None = None
    created_at: datetime | None = None


class ExistingProject(BaseModel):
    """Projet déjà là (existant, en cours, prévu ou terminé) dont une initiative peut dépendre."""

    model_config = ConfigDict(frozen=True)

    id: str
    dossier_id: str
    title: str
    state: ProjectState = "existing"
    duration_weeks: int | None = None
    depends_on: list[str] = []  # identifiants d'autres projets du dossier
    source_ids: list[str] = []
    author_id: str | None = None
    created_at: datetime | None = None
