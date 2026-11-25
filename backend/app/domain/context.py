"""Fiche de contexte d'un dossier (FR-25) : renseignée par formulaire ou chat, confirmée avant usage."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProjectType = Literal[
    "software", "data_ai", "infrastructure", "supplies", "services", "study", "change", "training"]
PROJECT_TYPES: tuple[str, ...] = (
    "software", "data_ai", "infrastructure", "supplies", "services", "study", "change", "training")

PROJECT_TYPE_LABELS: dict[str, dict[str, str]] = {
    "fr": {"software": "Logiciel et SI", "data_ai": "Données et IA",
           "infrastructure": "Infrastructure et travaux", "supplies": "Fournitures",
           "services": "Services et externalisation", "study": "Étude et conseil",
           "change": "Organisation et conduite du changement", "training": "Formation"},
    "en": {"software": "Software and IS", "data_ai": "Data and AI",
           "infrastructure": "Infrastructure and works", "supplies": "Supplies",
           "services": "Services and outsourcing", "study": "Study and advisory",
           "change": "Organisation and change management", "training": "Training"},
}

# Champs texte de la fiche (hors types de projet) et longueur maximale de chacun.
TEXT_FIELDS: dict[str, int] = {
    "sector": 200, "size": 200, "country": 100, "language": 50,
    "scope": 2000, "constraints": 2000, "stakeholders": 2000, "roadmap_axes": 1000,
}
FIELDS: tuple[str, ...] = (*TEXT_FIELDS, "project_types")


class ContextData(BaseModel):
    """Contenu de la fiche. Tout est facultatif : une fiche vide est une fiche valide."""

    model_config = ConfigDict(extra="forbid")

    sector: str = Field(default="", max_length=200)
    size: str = Field(default="", max_length=200)
    country: str = Field(default="", max_length=100)
    language: str = Field(default="", max_length=50)
    project_types: list[ProjectType] = []
    scope: str = Field(default="", max_length=2000)
    constraints: str = Field(default="", max_length=2000)
    stakeholders: str = Field(default="", max_length=2000)
    # Axes imposés à la feuille de route (un par ligne ou séparés par « ; »), ex. « Gouvernance ; Sécurité »
    roadmap_axes: str = Field(default="", max_length=1000)

    def missing(self) -> list[str]:
        """Champs encore vides : le chat pose ces questions."""
        return [f for f in FIELDS if not getattr(self, f)]


class ContextSheet(BaseModel):
    model_config = ConfigDict(frozen=True)

    dossier_id: str
    data: ContextData
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None

    @property
    def confirmed(self) -> bool:
        return self.confirmed_at is not None
