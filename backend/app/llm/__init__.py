from .base import LLMError, LLMProvider
from .fake import FakeProvider
from .ollama import OllamaProvider

__all__ = ["FakeProvider", "LLMError", "LLMProvider", "OllamaProvider", "build_provider"]


def build_provider(settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        return FakeProvider()
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings.ollama_base_url, settings.ollama_generation_model,
                              settings.ollama_embedding_model, settings.allowed_hosts,
                              settings.llm_timeout_seconds)
    raise LLMError(f"LLM_PROVIDER inconnu : {settings.llm_provider!r} (fake | ollama)")
