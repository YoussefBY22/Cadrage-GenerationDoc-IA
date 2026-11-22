"""Feuille de route : critères, initiatives, résultat du calcul de priorité."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Criterion(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    weight: float
    higher_is_better: bool = True


class CriterionScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    value: int  # 1..5
    source_ids: list[str]
    rationale: str


class Initiative(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    description: str
    finding_ids: list[str]
    scores: list[CriterionScore]
    depends_on: list[str] = []  # autres initiatives
    duration_weeks: int | None = None  # saisi par le consultant
    objective: str = ""
    expected_result: str = ""
    indicator: str = ""
    priority_ids: list[str] = []  # priorités institutionnelles liées
    depends_on_projects: list[str] = []  # projets existants dont elle dépend
    # objectif, résultat, indicateur : proposition IA tant qu'un humain ne l'a pas acceptée
    proposal_status: Literal["proposed", "accepted"] = "proposed"
    proposal_flags: list[str] = []  # nombres de la proposition absents des sources


class ScoredInitiative(BaseModel):
    model_config = ConfigDict(frozen=True)

    initiative: Initiative
    score: float
    rank: int
    wave: int
    unscored: list[str] = []  # critères sans note : « non évalué », jamais un score bas calculé


class RejectedLink(BaseModel):
    """Lien proposé par le modèle vers un identifiant qui n'a pas été fourni : écarté et signalé."""

    model_config = ConfigDict(frozen=True)

    initiative: str  # titre proposé par le modèle
    kind: str  # finding | priority | project | initiative
    value: str


class RoadmapResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    criteria: list[Criterion]
    items: list[ScoredInitiative]
    topo_order: list[str]
    cycles: list[list[str]]
    critical_path: list[str]
    rejected_links: list[RejectedLink] = []
    passages_not_sent: int = 0  # passages cités par les constats mais non envoyés (contexte plein)
