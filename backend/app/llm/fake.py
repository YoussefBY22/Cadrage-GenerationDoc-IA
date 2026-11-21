"""Faux modèle déterministe : permet de tester toute la chaîne sans GPU ni téléchargement.

Il ne « comprend » rien : même entrée -> même sortie, toujours. Les tests peuvent lui imposer des
réponses (`script`) pour simuler un modèle qui triche (fausse citation, chiffre inventé, etc.).
"""

import hashlib
import json
import math
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from .base import LLMError, LLMProvider, T

EMBEDDING_DIM = 64
_TOKEN = re.compile(r"\w+", re.UNICODE)


def _hash_int(text: str, salt: str = "") -> int:
    return int.from_bytes(hashlib.sha256((salt + text).encode()).digest()[:8], "big")


def hash_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Sac de mots hachés, normalisé : deux textes qui partagent des mots sont proches.

    Ce n'est PAS un embedding sémantique, juste un substitut déterministe pour les tests.
    """
    vec = [0.0] * dim
    for tok in _TOKEN.findall(text.lower()):
        h = _hash_int(tok)
        vec[h % dim] += 1.0 if (h >> 32) % 2 == 0 else -1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def _fill(schema: dict, root: dict, seed_text: str, depth: int = 0) -> Any:
    """Construit une valeur minimale valide pour un schéma JSON, de façon déterministe."""
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        return _fill(node, root, seed_text, depth + 1)
    if "enum" in schema:
        return schema["enum"][_hash_int(seed_text) % len(schema["enum"])]
    if "const" in schema:
        return schema["const"]
    for key in ("anyOf", "oneOf"):
        if key in schema:
            options = [o for o in schema[key] if o.get("type") != "null"] or schema[key]
            return _fill(options[0], root, seed_text, depth + 1)
    if "allOf" in schema:
        return _fill(schema["allOf"][0], root, seed_text, depth + 1)
    kind = schema.get("type")
    if kind == "object":
        props = schema.get("properties", {})
        return {k: _fill(v, root, seed_text + k, depth + 1) for k, v in props.items()}
    if kind == "array":
        if depth > 6:
            return []
        n = max(schema.get("minItems", 0), 1)
        return [_fill(schema.get("items", {}), root, f"{seed_text}[{i}]", depth + 1)
                for i in range(n)]
    if kind == "integer":
        return max(schema.get("minimum", 0), 1)
    if kind == "number":
        return float(max(schema.get("minimum", 0), 1))
    if kind == "boolean":
        return False
    if kind == "null":
        return None
    return f"valeur-{_hash_int(seed_text) % 10000:04d}"


class FakeProvider(LLMProvider):
    name = "fake-v1"

    def __init__(self, script: list[tuple[str, Any]] | None = None,
                 handler: Callable[[str, type[BaseModel]], Any] | None = None) -> None:
        """`script` : liste de (sous-chaîne du prompt, réponse imposée). Première règle qui
        correspond gagne. Une réponse peut être un str (texte), un dict/BaseModel (JSON).
        `handler` : fonction (prompt, schéma) -> dict, pour des cas dynamiques."""
        self.script = script or []
        self.handler = handler
        self.calls: list[dict] = []   # historique, utile pour les tests

    # -- capacités ---------------------------------------------------------------------------
    def generate(self, prompt, *, system=None, temperature=0.0, seed=0, max_tokens=None) -> str:
        self.calls.append({"kind": "generate", "prompt": prompt, "system": system})
        scripted = self._scripted(prompt)
        if scripted is not None:
            return scripted if isinstance(scripted, str) else json.dumps(scripted)
        return f"[réponse simulée {_hash_int(prompt) % 100000:05d}]"

    def generate_structured(self, prompt, schema: type[T], *, system=None, temperature=0.0,
                            seed=0) -> T:
        self.calls.append({"kind": "structured", "prompt": prompt, "system": system,
                           "schema": schema.__name__})
        scripted = self._scripted(prompt)
        if scripted is None and self.handler is not None:
            scripted = self.handler(prompt, schema)
        if scripted is None:
            scripted = _fill(schema.model_json_schema(), schema.model_json_schema(), prompt)
        try:
            if isinstance(scripted, BaseModel):
                scripted = scripted.model_dump()
            if isinstance(scripted, str):
                return schema.model_validate_json(scripted)
            return schema.model_validate(scripted)
        except ValidationError as exc:
            raise LLMError(f"Réponse non conforme au schéma {schema.__name__}: {exc}") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [hash_embedding(t) for t in texts]

    @property
    def embedding_dimension(self) -> int:
        return EMBEDDING_DIM

    def _scripted(self, prompt: str) -> Any | None:
        for needle, answer in self.script:
            if needle in prompt:
                return answer
        return None
