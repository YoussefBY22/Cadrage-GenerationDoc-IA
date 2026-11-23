"""Chargement et validation des gabarits YAML de livrables."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from app.domain.decisions import DecisionCategory
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
    # Références courtes (jamais de texte protégé) : elles cadrent la structure, jamais une preuve.
    referentiels: list[str] = Field(default_factory=list)
    # Catégories de décision humaine CONFIRMÉE sans lesquelles la section est refusée, sans appel
    # au modèle : budget, profil, calendrier… ne figurent jamais dans un diagnostic.
    requires_decisions: list[DecisionCategory] = Field(default_factory=list)


class Template(BaseModel):
    id: str
    version: str
    type: DeliverableType
    language: Lang
    title: str
    referentiels: list[str] = Field(default_factory=list)
    sections: list[SectionSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _keys_uniques(self) -> Template:
        keys = [s.key for s in self.sections]
        if len(keys) != len(set(keys)):
            raise ValueError("clés de section en double")
        return self


class AdaptSpec(BaseModel):
    """Retouche d'une section du tronc commun par un module (rien n'est retiré, tout s'ajoute)."""

    key: str
    instructions_append: str = ""
    queries_add: list[str] = Field(default_factory=list)
    referentiels_add: list[str] = Field(default_factory=list)
    requires_decisions_add: list[DecisionCategory] = Field(default_factory=list)


class ModuleSection(SectionSpec):
    after: str | None = None  # clé de la section après laquelle s'insérer (défaut : en fin)


class ModuleVariant(BaseModel):
    sections: list[ModuleSection] = Field(default_factory=list)
    adapt: list[AdaptSpec] = Field(default_factory=list)


class ModuleLang(BaseModel):
    label: str
    referentiels: list[str] = Field(default_factory=list)
    tor: ModuleVariant = Field(default_factory=ModuleVariant)
    cdc: ModuleVariant = Field(default_factory=ModuleVariant)


class ProjectModule(BaseModel):
    id: str
    version: str
    fr: ModuleLang
    en: ModuleLang


def load_module(module_id: str) -> ProjectModule:
    path = TEMPLATES_DIR / "modules" / f"{module_id}.yaml"
    if not path.is_file():
        raise TemplateError(f"module inconnu : {module_id}")
    try:
        mod = ProjectModule.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (yaml.YAMLError, ValueError) as exc:
        raise TemplateError(f"module invalide {path.name} : {exc}") from exc
    if mod.id != module_id:
        raise TemplateError(f"module incohérent : {path.name}")
    return mod


def available_modules() -> list[str]:
    """Identifiants des modules livrés, dans l'ordre canonique des types de projet."""
    from app.domain.context import PROJECT_TYPES

    present = {p.stem for p in (TEMPLATES_DIR / "modules").glob("*.yaml")}
    return [m for m in PROJECT_TYPES if m in present]


def _merge(base: Template, modules: list[str]) -> Template:
    """Tronc commun + modules. Ordre canonique : le même choix donne toujours le même gabarit."""
    if base.type not in ("tor", "cdc"):
        return base
    canon = [m for m in available_modules() if m in set(modules)]
    unknown = [m for m in modules if m not in canon]
    if unknown:
        raise TemplateError("module inconnu : " + ", ".join(unknown))
    sections = [s.model_copy(deep=True) for s in base.sections]
    refs = list(base.referentiels)
    tails: dict[str, str] = {}  # dernière section insérée après chaque ancre : ordre canonique stable
    for mid in canon:
        mod = load_module(mid)
        lang: ModuleLang = getattr(mod, base.language)
        variant: ModuleVariant = getattr(lang, base.type)
        refs += [r for r in lang.referentiels if r not in refs]
        for ad in variant.adapt:
            target = next((s for s in sections if s.key == ad.key), None)
            if target is None:
                raise TemplateError(f"module {mid} : section à adapter inconnue : {ad.key}")
            if ad.instructions_append:
                target.instructions = f"{target.instructions} {ad.instructions_append}".strip()
            target.queries += [q for q in ad.queries_add if q not in target.queries]
            target.referentiels += [r for r in ad.referentiels_add if r not in target.referentiels]
            target.requires_decisions += [c for c in ad.requires_decisions_add
                                          if c not in target.requires_decisions]
        for ms in variant.sections:
            if any(s.key == ms.key for s in sections):
                raise TemplateError(f"module {mid} : clé de section en double : {ms.key}")
            anchor = ms.after or sections[-1].key
            if ms.after is not None and not any(s.key == anchor for s in sections):
                raise TemplateError(f"module {mid} : ancre inconnue : {anchor}")
            at = tails.get(anchor, anchor)
            idx = next(i for i, s in enumerate(sections) if s.key == at)
            spec = SectionSpec.model_validate(ms.model_dump(exclude={"after"}))
            sections.insert(idx + 1, spec)
            tails[anchor] = spec.key
    return base.model_copy(update={"sections": sections, "referentiels": refs})


def load_template(type: DeliverableType, lang: Lang = "fr", modules: Sequence[str] = ()) -> Template:
    """Charge le gabarit ``type`` dans la langue ``lang`` ; erreur claire si non traduit.

    ``modules`` : modules par type de projet, combinés au tronc commun (FR-24).
    """
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
    return _merge(tpl, list(modules)) if modules else tpl


def template_for(content) -> Template:
    """Gabarit exact d'un livrable : son type, sa langue et ses modules."""
    return load_template(content.type, content.language, getattr(content, "modules", ()))
