"""Décisions humaines (FR-23) : budget, profil, calendrier… Citables comme une source, jamais devinées."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DecisionCategory = Literal[
    "budget", "profile", "schedule", "duration", "criterion", "constraint", "other"]
DECISION_CATEGORIES: tuple[str, ...] = (
    "budget", "profile", "schedule", "duration", "criterion", "constraint", "other")
DecisionStatus = Literal["proposed", "confirmed"]

CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "fr": {"budget": "budget", "profile": "profil", "schedule": "calendrier", "duration": "durée",
           "criterion": "critère d'évaluation", "constraint": "contrainte", "other": "autre"},
    "en": {"budget": "budget", "profile": "profile", "schedule": "schedule", "duration": "duration",
           "criterion": "evaluation criterion", "constraint": "constraint", "other": "other"},
}


def category_label(category: str, lang: str = "fr") -> str:
    return CATEGORY_LABELS.get(lang, CATEGORY_LABELS["fr"]).get(category, category)


class Decision(BaseModel):
    """Décision d'un humain. Seule `confirmed` compte pour générer, vérifier et exporter."""

    model_config = ConfigDict(frozen=True)

    id: str
    dossier_id: str
    category: DecisionCategory
    text: str
    status: DecisionStatus = "proposed"
    author_id: str | None = None
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    created_at: datetime | None = None
