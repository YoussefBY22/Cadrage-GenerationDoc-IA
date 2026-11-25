"""Ordre des propriétés d'une réponse d'entraînement = ordre du schéma JSON envoyé au moteur.

Ollama contraint la sortie par une grammaire tirée du schéma ; elle impose l'ORDRE des propriétés. Si une réponse
d'entraînement écrit ``missing_evidence`` avant ``sentences``, le modèle apprend à clore l'objet sans phrase.
L'ordre est donc déduit du schéma lui-même (``model_json_schema``), jamais écrit à la main.
"""

from __future__ import annotations

import json

from pydantic import BaseModel


def _resolve(schema: dict, defs: dict) -> dict:
    ref = schema.get("$ref")
    if ref:
        return defs[ref.rsplit("/", 1)[-1]]
    for alt in schema.get("anyOf", []):  # Optional[...] : on prend la branche objet ou liste
        if alt.get("type") != "null":
            return _resolve(alt, defs)
    return schema


def _order(value, schema: dict, defs: dict):
    schema = _resolve(schema, defs)
    if isinstance(value, dict) and "properties" in schema:
        props = schema["properties"]
        unknown = set(value) - set(props)
        if unknown:
            raise ValueError(f"propriétés absentes du schéma : {sorted(unknown)}")
        return {k: _order(value[k], props[k], defs) for k in props if k in value}
    if isinstance(value, list) and "items" in schema:
        return [_order(v, schema["items"], defs) for v in value]
    return value


def ordered(model: type[BaseModel], answer: dict) -> dict:
    """``answer`` avec ses clés (à tous les niveaux) dans l'ordre des propriétés du schéma de ``model``."""
    schema = model.model_json_schema()
    return _order(answer, schema, schema.get("$defs", {}))


def dumps(model: type[BaseModel], answer: dict) -> str:
    return json.dumps(ordered(model, answer), ensure_ascii=False)


def is_ordered(model: type[BaseModel], answer: dict) -> bool:
    """Vrai si les clés de ``answer`` suivent déjà l'ordre du schéma (comparaison des listes de clés, récursive)."""
    return json.dumps(ordered(model, answer)) == json.dumps(answer)
