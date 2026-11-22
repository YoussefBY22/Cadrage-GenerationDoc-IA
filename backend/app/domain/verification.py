"""Vérification phrase par phrase."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

IssueCode = Literal[
    "UNKNOWN_SOURCE",
    "FOREIGN_SOURCE",
    "NUMBER_NOT_FOUND",
    "FACT_WITHOUT_SOURCE",
    "LOW_SUPPORT",
    "INSTRUCTION_ECHO",
    "UNKNOWN_FINDING",
    "TRANSITION_WITH_NUMBER",
    "RANGE_LOST",
]


class Issue(BaseModel):
    model_config = ConfigDict(frozen=True)

    sentence_index: int
    code: IssueCode
    severity: Literal["blocking", "warning"]
    detail: str


class SentenceCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    status: Literal["verified", "warning", "failed"]
    numbers_cited: int
    numbers_found: int
    support: float  # 0..1


class VerificationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_key: str
    checks: list[SentenceCheck]
    issues: list[Issue]

    @property
    def tpv(self) -> float:
        """Taux de phrases vérifiées ; 1.0 s'il n'y a aucune phrase (refus)."""
        if not self.checks:
            return 1.0
        return sum(c.status == "verified" for c in self.checks) / len(self.checks)
