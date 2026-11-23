"""Schémas JSON envoyés au modèle (volontairement petits ; étiquettes courtes P3 / F2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SentenceKind = Literal["fact", "recommendation", "transition"]
Status = Literal["ok", "insufficient_evidence"]


class LLMSentence(BaseModel):
    text: str
    kind: SentenceKind
    sources: list[str]
    findings: list[str] = []
    decisions: list[str] = []


class LLMSection(BaseModel):
    status: Status
    sentences: list[LLMSentence] = []
    missing_evidence: str | None = None


Stance = Literal["accept", "partial", "reject", "conflict", "aligned"]


class LLMStance(BaseModel):
    """Position d'une institution sur une recommandation, ou conflit avec une stratégie / une contrainte.

    L'ordre des propriétés est celui que la grammaire d'Ollama impose : `stance` avant `sentences`.
    """

    status: Status
    stance: Stance | None = None
    sentences: list[LLMSentence] = []
    missing_evidence: str | None = None


class LLMFinding(BaseModel):
    text: str
    theme: str
    severity: Literal["low", "medium", "high"]
    sources: list[str]


class LLMFindings(BaseModel):
    status: Status
    findings: list[LLMFinding] = []


class LLMScore(BaseModel):
    key: str
    value: int = Field(ge=1, le=5)
    sources: list[str]
    rationale: str


class LLMInitiative(BaseModel):
    title: str
    description: str
    findings: list[str]
    scores: list[LLMScore]
    depends_on_titles: list[str] = []
    objective: str = ""
    expected_result: str = ""
    indicator: str = ""
    priorities: list[str] = []  # étiquettes PR1..PRn fournies, jamais d'autre identifiant
    depends_on_projects: list[str] = []  # étiquettes PJ1..PJn fournies


class LLMInitiatives(BaseModel):
    initiatives: list[LLMInitiative]


def _all_required(schema: dict, _cls=None) -> None:
    """Tous les champs sont REQUIS dans le schéma envoyé au moteur (un petit modèle omet les facultatifs)."""
    schema["required"] = list(schema.get("properties", {}))


def build_initiatives_schema(finding_labels: list[str], priority_labels: list[str],
                             project_labels: list[str], criteria_keys: list[str]):
    """Schéma de `LLMInitiatives` construit pour CET appel : champs requis, étiquettes réellement fournies.

    Les contraintes (champs requis, enum, nombre de notes) sont dans le schéma JSON envoyé au moteur ;
    la validation locale reste tolérante : un identifiant inventé est rejeté ET signalé par le service,
    une note manquante reste « non évalué », un champ omis reste vide (et visible comme tel).
    """
    from pydantic import ConfigDict, create_model

    cfg = ConfigDict(json_schema_extra=_all_required)

    def labels(values: list[str]):
        extra = ({"items": {"type": "string", "enum": list(values)}} if values
                 else {"maxItems": 0})
        return Field(default_factory=list, json_schema_extra=extra)

    score = create_model(
        "LLMScore", __base__=LLMScore, __config__=cfg,
        key=(str, Field(json_schema_extra={"enum": list(criteria_keys)})))
    n = len(criteria_keys)
    ini = create_model(
        "LLMInitiative", __config__=cfg,
        title=(str, ...), description=(str, ...),
        findings=(list[str], labels(finding_labels)),
        scores=(list[score], Field(default_factory=list,
                                   json_schema_extra={"minItems": n, "maxItems": n})),
        depends_on_titles=(list[str], Field(default_factory=list)),
        objective=(str, ""), expected_result=(str, ""), indicator=(str, ""),
        priorities=(list[str], labels(priority_labels)),
        depends_on_projects=(list[str], labels(project_labels)))
    return create_model("LLMInitiatives", initiatives=(list[ini], ...))
