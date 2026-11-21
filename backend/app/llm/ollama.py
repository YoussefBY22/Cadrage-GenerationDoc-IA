"""Fournisseur réel : Ollama, sur la machine du client. NON testé dans le cloud (pas de modèle).

Il est vérifié par un test de contrat contre un serveur simulé (tests/test_ollama_contract.py).
Garde-fou confidentialité : l'adresse du serveur doit être locale ou explicitement autorisée.
"""

import json
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from .base import LLMError, LLMProvider, T


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, generation_model: str, embedding_model: str,
                 allowed_hosts: set[str], timeout: float = 120.0,
                 client: httpx.Client | None = None) -> None:
        host = urlparse(base_url).hostname or ""
        if host not in allowed_hosts:
            raise LLMError(
                f"Hôte de modèle refusé : {host!r}. Autorisés : {sorted(allowed_hosts)} "
                "(le produit ne doit parler qu'à un serveur local)."
            )
        if not generation_model or not embedding_model:
            raise LLMError("OLLAMA_GENERATION_MODEL et OLLAMA_EMBEDDING_MODEL doivent être définis.")
        self.base_url = base_url.rstrip("/")
        self.generation_model = generation_model
        self.embedding_model = embedding_model
        self.name = f"ollama:{generation_model}"
        self._client = client or httpx.Client(timeout=timeout, trust_env=False)
        self._dim: int | None = None

    def _post(self, path: str, payload: dict) -> dict:
        try:
            resp = self._client.post(f"{self.base_url}{path}", json=payload)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"Appel Ollama {path} échoué : {exc}") from exc

    @staticmethod
    def _messages(prompt: str, system: str | None) -> list[dict]:
        msgs = [{"role": "system", "content": system}] if system else []
        return msgs + [{"role": "user", "content": prompt}]

    def _chat(self, prompt, system, temperature, seed, fmt=None, max_tokens=None) -> str:
        options: dict = {"temperature": temperature}
        if seed is not None:
            options["seed"] = seed
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        payload = {"model": self.generation_model, "messages": self._messages(prompt, system),
                   "stream": False, "options": options}
        if fmt is not None:
            payload["format"] = fmt
        data = self._post("/api/chat", payload)
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMError("Réponse Ollama /api/chat inattendue") from exc

    def generate(self, prompt, *, system=None, temperature=0.0, seed=0, max_tokens=None) -> str:
        return self._chat(prompt, system, temperature, seed, max_tokens=max_tokens)

    def generate_structured(self, prompt, schema: type[T], *, system=None, temperature=0.0,
                            seed=0) -> T:
        raw = self._chat(prompt, system, temperature, seed, fmt=schema.model_json_schema())
        try:
            return schema.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise LLMError(f"Sortie non conforme au schéma {schema.__name__}: {exc}") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post("/api/embed", {"model": self.embedding_model, "input": texts})
        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise LLMError("Réponse Ollama /api/embed inattendue")
        if vectors:
            self._dim = len(vectors[0])
        return vectors

    @property
    def embedding_dimension(self) -> int:
        if self._dim is None:
            self.embed(["dimension"])
        return self._dim or 0
