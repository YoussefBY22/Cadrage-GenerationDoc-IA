"""Chargement et validation des gabarits YAML de livrables."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from app.domain.ids import DeliverableType, Lang

TEMPLATES_DIR = Path(__file__).parent / "templates"


class TemplateError(Exception):
    """Gabarit absent, non traduit ou invalide."""


class SectionSpec(BaseModel):
    key: str
    title: str
    instructions: str
    queries: list[str] = Field(min_length=2)
    min_sources: int = Field(default=1, ge=1)
    max_sentences: int = Field(default=12, ge=1)
    uses_findings: bool = False


class Template(BaseModel):
    id: str
    version: str
    type: DeliverableType
    language: Lang
    title: str
    sections: list[SectionSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _keys_uniques(self) -> Template:
        keys = [s.key for s in self.sections]
        if len(keys) != len(set(keys)):
            raise ValueError("clés de section en double")
        return self


def load_template(type: DeliverableType, lang: Lang = "fr") -> Template:
    """Charge le gabarit ``type`` dans la langue ``lang`` ; erreur claire si non traduit."""
    path = TEMPLATES_DIR / lang / f"{type}.yaml"
    if not path.is_file():
        raise TemplateError(f"gabarit non traduit : {type} ({lang})")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        tpl = Template.model_validate(data)
    except (yaml.YAMLError, ValueError) as exc:
        raise TemplateError(f"gabarit invalide {path.name} : {exc}") from exc
    if tpl.type != type or tpl.language != lang:
        raise TemplateError(f"gabarit incohérent : {path.name}")
    return tpl
