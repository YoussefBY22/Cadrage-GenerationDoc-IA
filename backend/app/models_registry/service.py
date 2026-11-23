"""Cas d'usage du registre, partagés par l'API et la ligne de commande."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider

from .engine import EngineClient, describe, is_embedding_only
from .errors import RegistryError
from .limits import build_limits, context_budget
from .probe import run_probe
from .store import RegistryStore

REINDEX_MESSAGE = ("Changer le modèle d'embeddings exige une réindexation de tous les documents : "
                   "réindexation requise.")


def _candidate(settings, name: str) -> OllamaProvider:
    return OllamaProvider(
        settings.ollama_base_url, name, settings.ollama_embedding_model or "n/a",
        settings.allowed_hosts, settings.llm_timeout_seconds, think=settings.ollama_think,
        temperature=settings.ollama_temperature, keep_alive=settings.ollama_keep_alive,
        options={"num_ctx": settings.ollama_num_ctx, "num_gpu": settings.ollama_num_gpu,
                 "num_predict": settings.ollama_num_predict, "top_p": settings.ollama_top_p,
                 "top_k": settings.ollama_top_k, "repeat_penalty": settings.ollama_repeat_penalty})


class RegistryService:
    def __init__(self, settings, *, engine: EngineClient | None = None,
                 store: RegistryStore | None = None,
                 provider_factory: Callable[[str], LLMProvider] | None = None) -> None:
        self.settings = settings
        self.engine = engine or EngineClient(settings.ollama_base_url, settings.allowed_hosts)
        self.store = store or RegistryStore(settings.models_registry_path)
        self._factory = provider_factory or (lambda name: _candidate(settings, name))

    @property
    def demo(self) -> bool:
        """Fournisseur « fake » ou « demo » : le modèle de langage n'est pas utilisé, activer ne changerait rien."""
        return self.settings.llm_provider != "ollama"

    def _refuse_in_demo(self) -> None:
        if self.demo:
            raise RegistryError(409, "DEMO_MODE",
                                "Mode démonstration : le modèle de langage n'est pas utilisé.")

    # --- lecture ----------------------------------------------------------------------------------
    @property
    def base_model(self) -> str | None:
        return self.settings.ollama_generation_model or None

    def current(self) -> str | None:
        """Modèle en service : le choix du registre, sinon celui de la configuration."""
        return self.store.active() or self.base_model

    def _card(self, tag: dict) -> dict:
        try:
            return describe(tag, self.engine.show(tag.get("name") or tag.get("model")))
        except RegistryError:
            return describe(tag)

    def list(self) -> dict:
        try:
            tags = self.engine.tags()
            reachable = True
        except RegistryError:
            tags, reachable = [], False
        state = self.store.load()
        current = state["active"] or self.base_model
        loaded = {m.get("name") or m.get("model"): m for m in self.engine.loaded()} if reachable else {}
        models = []
        for tag in tags:
            card = self._card(tag)
            test = state["tests"].get(card["name"])
            card.update(
                active=card["name"] == current,
                role="embedding" if is_embedding_only(card) else "generation",
                test=_summary(test, card, self.settings))
            models.append(card)
        active_card = next((m for m in models if m["active"]), None)
        return {
            "engine": {"reachable": reachable, "provider": self.settings.llm_provider, "demo": self.demo},
            "active": current, "configured": self.base_model,
            "embedding_model": self.settings.ollama_embedding_model or None,
            "previous": self.store.previous_model(current),
            "models": models, "history": state["history"][-20:][::-1],
            "limits": build_limits(self.settings, active_card, loaded.get(current)),
            "context": context_budget(self.settings, active_card["max_context"] if active_card else None),
        }

    def context(self, candidate_tokens: int | None = None) -> dict:
        card = self._installed(self.current(), required=False)
        return context_budget(self.settings, card["max_context"] if card else None, candidate_tokens)

    def _installed(self, name: str | None, *, required: bool = True) -> dict | None:
        if name:
            for tag in self.engine.tags():
                if name in (tag.get("name"), tag.get("model")):
                    return self._card(tag)
        if required:
            raise RegistryError(404, "MODEL_NOT_INSTALLED",
                                f"Modèle non installé dans le moteur local : {name!r}")
        return None

    # --- test -------------------------------------------------------------------------------------
    def test(self, name: str) -> dict:
        self._refuse_in_demo()
        card = self._installed(name)
        allocated = self.settings.ollama_num_ctx or _default_ctx()
        report = run_probe(self._factory(name), card, allocated)
        report |= {"model": name, "digest": card["digest"],
                   "at": datetime.now(UTC).isoformat(timespec="seconds")}
        self.store.record_test(name, report)
        return report

    # --- activation et retour arrière -------------------------------------------------------------
    def activate(self, name: str, *, by: str | None = None, role: str = "generation") -> dict:
        self._refuse_in_demo()
        if role == "embedding":
            raise RegistryError(409, "REINDEX_REQUIRED", REINDEX_MESSAGE)
        card = self._installed(name)
        if is_embedding_only(card):
            raise RegistryError(409, "REINDEX_REQUIRED", REINDEX_MESSAGE)
        test = self.store.last_test(name)
        if (not test or not test.get("passed") or test.get("digest") != card["digest"]
                or test.get("num_ctx") != (self.settings.ollama_num_ctx or _default_ctx())):
            raise RegistryError(409, "TEST_REQUIRED",
                                "Un test réussi et à jour est exigé avant l'activation de ce modèle.")
        previous = self.current()
        entry = self.store.set_active(name, by=by, action="activate", base=self.base_model)
        return {"active": name, "previous": previous, "entry": entry}

    def rollback(self, *, by: str | None = None) -> dict:
        self._refuse_in_demo()
        current = self.current()
        target = self.store.previous_model(current)
        if not target:
            raise RegistryError(409, "NO_PREVIOUS_MODEL", "Aucun modèle précédent vers lequel revenir.")
        self._installed(target)  # le modèle précédent doit toujours être installé
        entry = self.store.set_active(target, by=by, action="rollback", base=self.base_model)
        return {"active": target, "previous": current, "entry": entry}


def _default_ctx() -> int:
    from app.llm.ollama import DEFAULT_NUM_CTX

    return DEFAULT_NUM_CTX


def _summary(test: dict | None, card: dict, settings) -> dict | None:
    if not test:
        return None
    current = (test.get("digest") == card["digest"]
               and test.get("num_ctx") == (settings.ollama_num_ctx or _default_ctx()))
    return {"passed": test["passed"], "at": test["at"], "up_to_date": current,
            "tokens_per_second": test.get("tokens_per_second"), "checks": test["checks"]}
