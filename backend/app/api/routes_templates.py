"""Gabarits par type de projet (FR-24) : aperçu des sections et des décisions exigées."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.domain.context import PROJECT_TYPE_LABELS
from app.domain.decisions import category_label
from app.generation.template_loader import TemplateError, available_modules, load_template
from app.services import User, error_response

router = APIRouter(tags=["templates"])


@router.get("/templates/modules")
def list_modules(user: User, language: Literal["fr", "en"] = "fr"):
    labels = PROJECT_TYPE_LABELS[language]
    return [{"id": m, "label": labels[m]} for m in available_modules()]


@router.get("/templates/{type}")
def preview(type: Literal["tor", "cdc"], user: User, language: Literal["fr", "en"] = "fr",
            modules: Annotated[list[str] | None, Query()] = None):
    """Sections du gabarit pour ce choix de modules, avec les décisions humaines qu'elles exigent."""
    modules = modules or []
    try:
        tpl = load_template(type, language, modules)
    except TemplateError as exc:
        return error_response(422, "BAD_MODULE", str(exc))
    return {"id": tpl.id, "title": tpl.title, "modules": modules, "referentiels": tpl.referentiels,
            "sections": [{"key": s.key, "title": s.title,
                          "requires_decisions": list(s.requires_decisions),
                          "requires_labels": [category_label(c, language) for c in s.requires_decisions]}
                         for s in tpl.sections]}
