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


class LLMSection(BaseModel):
    status: Status
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


class LLMInitiatives(BaseModel):
    initiatives: list[LLMInitiative]
