"""Génération : phrases ancrées, sections, constats, contenu d'un livrable."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .ids import DeliverableType, Lang
from .roadmap import RoadmapResult

SentenceKind = Literal["fact", "recommendation", "transition"]


class Sentence(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    kind: SentenceKind
    source_labels: list[str] = []  # ["P2","P5"] tel que rendu par le modèle
    source_ids: list[str] = []  # chunk ids, résolus par le code
    finding_ids: list[str] = []
    decision_ids: list[str] = []  # décisions humaines confirmées citées (D1..Dn résolus)


class SectionDraft(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_key: str
    status: Literal["ok", "insufficient_evidence"]
    sentences: list[Sentence]
    missing_evidence: str | None = None


class Finding(BaseModel):
    """Un « constat » (preuve d'abord)."""

    model_config = ConfigDict(frozen=True)

    id: str
    dossier_id: str
    text: str
    theme: str
    severity: Literal["low", "medium", "high"]
    source_ids: list[str]
    validated: bool = False


class DeliverableContent(BaseModel):
    """Contenu d'une version de livrable."""

    model_config = ConfigDict(frozen=True)

    type: DeliverableType
    language: Lang
    template_id: str
    template_version: str
    sections: list[SectionDraft]
    roadmap: RoadmapResult | None = None
    modules: list[str] = []  # modules par type de projet combinés au tronc commun (FR-24)
