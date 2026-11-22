"""Fournisseur réel : Ollama, sur la machine du client.

Vérifié par un test de contrat contre un serveur simulé (tests/test_ollama_contract.py) et par un
test de fumée contre un vrai Ollama (tests/llm/test_ollama_smoke.py, marqueur `ollama`).
Garde-fou confidentialité : l'adresse du serveur doit être locale ou explicitement autorisée.

Réglages propres à Qwen3 : la « réflexion » est désactivée (`think: false`), sinon le modèle
consomme son budget de jetons à raisonner et la latence explose ; les sorties structurées passent
par `format` = schéma JSON (décodage contraint).
"""

import json
from collections.abc import Callable
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from .base import LLMError, LLMProvider, T

DEFAULT_NUM_CTX = 4096  # ce que tient un GPU de 4 Go (mesuré le 22/11/2026)


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, generation_model: str, embedding_model: str,
                 allowed_hosts: set[str], timeout: float = 120.0,
                 client: httpx.Client | None = None, *, think: bool = False,
                 options: dict | None = None, keep_alive: str | None = "30m",
                 query_prefix: str = "", passage_prefix: str = "",
                 embed_batch: int = 32, temperature: float | None = None,
                 model_resolver: Callable[[], str | None] | None = None) -> None:
        host = urlparse(base_url).hostname or ""
        if host not in allowed_hosts:
            raise LLMError(
                f"Hôte de modèle refusé : {host!r}. Autorisés : {sorted(allowed_hosts)} "
                "(le produit ne doit parler qu'à un serveur local)."
            )
        if not generation_model or not embedding_model:
            raise LLMError("OLLAMA_GENERATION_MODEL et OLLAMA_EMBEDDING_MODEL doivent être définis.")
        self.base_url = base_url.rstrip("/")
        self.base_generation_model = generation_model
        # Modèle actif choisi dans le registre : relu à chaque appel, donc pris en compte sans redémarrage.
        self.model_resolver = model_resolver
        self.embedding_model = embedding_model
        # connexion courte (serveur local absent = échec rapide), lecture longue (génération)
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout, connect=min(10.0, timeout)), trust_env=False)
        self.think = think
        self.temperature = temperature  # impose la température (ignore celle de l'appelant)
        self.extra_options = {k: v for k, v in (options or {}).items() if v is not None}
        self.keep_alive = keep_alive
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self.embed_batch = max(1, embed_batch)
        self._dim: int | None = None
        self.last_usage: dict = {}
        self.context_tokens = int(self.extra_options.get("num_ctx") or DEFAULT_NUM_CTX)
        self.extra_options["num_ctx"] = self.context_tokens  # explicite : le défaut d'Ollama varie selon la VRAM

    @property
    def generation_model(self) -> str:
        if self.model_resolver is not None:
            try:
                chosen = self.model_resolver()
            except Exception:  # noqa: BLE001 — un registre illisible ne doit pas arrêter la génération
                chosen = None
            if chosen:
                return chosen
        return self.base_generation_model

    @property
    def name(self) -> str:
        """Nom exact du modèle en service, tracé dans chaque exécution (NFR-07)."""
        return f"ollama:{self.generation_model}"

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
        options: dict = {**self.extra_options,
                         "temperature": temperature if self.temperature is None else self.temperature}
        if seed is not None:
            options["seed"] = seed
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        payload = {"model": self.generation_model, "messages": self._messages(prompt, system),
                   "stream": False, "think": self.think, "options": options,
                   # jamais de coupe silencieuse : par défaut Ollama jette le DÉBUT (règles, premiers passages)
                   "truncate": False, "shift": False}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        if fmt is not None:
            payload["format"] = fmt
        data = self._post("/api/chat", payload)
        self.last_usage = {"prompt_tokens": data.get("prompt_eval_count"),
                           "output_tokens": data.get("eval_count"),
                           "total_ms": (data.get("total_duration") or 0) // 1_000_000}
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

    def _embed(self, texts: list[str], prefix: str) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.embed_batch):
            batch = [prefix + t for t in texts[i:i + self.embed_batch]]
            payload = {"model": self.embedding_model, "input": batch, "truncate": True}
            if self.keep_alive:
                payload["keep_alive"] = self.keep_alive
            vectors = self._post("/api/embed", payload).get("embeddings")
            if not isinstance(vectors, list) or len(vectors) != len(batch):
                raise LLMError("Réponse Ollama /api/embed inattendue")
            out += vectors
        if out:
            self._dim = len(out[0])
        return out

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Passages à indexer (préfixe « passage » du modèle, vide pour bge-m3)."""
        return self._embed(texts, self.passage_prefix)

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        """Requêtes de recherche (préfixe « query » du modèle, vide pour bge-m3)."""
        return self._embed(texts, self.query_prefix)

    @property
    def embedding_dimension(self) -> int:
        if self._dim is None:
            self.embed(["dimension"])
        return self._dim or 0
