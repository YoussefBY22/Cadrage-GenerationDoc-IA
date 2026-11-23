"""Lecture seule du moteur local (Ollama) : modèles installés, capacités, taille, contexte, licence.

Aucune écriture, aucun téléchargement. L'adresse vient de la configuration serveur et doit rester locale.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from .errors import RegistryError

LICENSE_MAX = 160


class EngineClient:
    def __init__(self, base_url: str, allowed_hosts: set[str], *, timeout: float = 10.0,
                 client: httpx.Client | None = None) -> None:
        host = urlparse(base_url).hostname or ""
        if host not in allowed_hosts:
            raise RegistryError(500, "ENGINE_HOST_REFUSED",
                                f"Hôte de modèle refusé : {host!r} (serveur local uniquement)")
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout, trust_env=False)

    def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        try:
            resp = self._client.request(method, f"{self.base_url}{path}", json=payload)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RegistryError(502, "ENGINE_UNREACHABLE",
                                f"Moteur local injoignable ({path}) : {exc}") from exc

    def tags(self) -> list[dict]:
        return list(self._call("GET", "/api/tags").get("models") or [])

    def show(self, name: str) -> dict:
        return self._call("POST", "/api/show", {"model": name})

    def loaded(self) -> list[dict]:
        """Modèles chargés en mémoire (contexte et mémoire vidéo réellement occupés) ; vide si indisponible."""
        try:
            return list(self._call("GET", "/api/ps").get("models") or [])
        except RegistryError:
            return []


def _max_context(info: dict) -> int | None:
    for key, value in info.items():
        if key.endswith(".context_length") and isinstance(value, int):
            return value
    return None


def describe(tag: dict, shown: dict | None = None) -> dict:
    """Fiche d'un modèle à partir de `/api/tags` (+ `/api/show` si fourni)."""
    shown = shown or {}
    details = shown.get("details") or tag.get("details") or {}
    caps = shown.get("capabilities")
    licence = (shown.get("license") or "").strip().splitlines()
    return {
        "name": tag.get("name") or tag.get("model"),
        "digest": tag.get("digest") or "",
        "size_bytes": tag.get("size"),
        "modified_at": tag.get("modified_at"),
        "family": details.get("family"),
        "parameter_size": details.get("parameter_size"),
        "quantization": details.get("quantization_level"),
        "max_context": _max_context(shown.get("model_info") or {}),
        "capabilities": caps if isinstance(caps, list) else None,  # None : moteur trop ancien pour les indiquer
        "license": licence[0][:LICENSE_MAX] if licence else None,
    }


def is_embedding_only(card: dict) -> bool:
    caps = card.get("capabilities")
    return bool(caps) and "completion" not in caps and "embedding" in caps
