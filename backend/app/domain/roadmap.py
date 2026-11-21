"""Feuille de route : critères, initiatives, résultat du calcul de priorité."""

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
    depends_on: list[str] = []
    duration_weeks: int | None = None  # saisi par le consultant


class ScoredInitiative(BaseModel):
    model_config = ConfigDict(frozen=True)

    initiative: Initiative
    score: float
    rank: int
    wave: int


class RoadmapResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    criteria: list[Criterion]
    items: list[ScoredInitiative]
    topo_order: list[str]
    cycles: list[list[str]]
    critical_path: list[str]
