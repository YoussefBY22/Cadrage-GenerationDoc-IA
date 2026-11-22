from .base import LLMError, LLMProvider
from .fake import FakeProvider
from .ollama import OllamaProvider

__all__ = ["FakeProvider", "LLMError", "LLMProvider", "OllamaProvider", "build_provider"]


def build_provider(settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        return FakeProvider()
    if settings.llm_provider == "demo":
        from .demo import demo_handler

        return FakeProvider(handler=demo_handler)
    if settings.llm_provider == "ollama":
        from app.models_registry.store import active_model_resolver

        return OllamaProvider(settings.ollama_base_url, settings.ollama_generation_model,
                              settings.ollama_embedding_model, settings.allowed_hosts,
                              settings.llm_timeout_seconds,
                              think=settings.ollama_think,
                              temperature=settings.ollama_temperature,
                              keep_alive=settings.ollama_keep_alive,
                              options={"num_ctx": settings.ollama_num_ctx,
                                       "num_gpu": settings.ollama_num_gpu,
                                       "num_predict": settings.ollama_num_predict,
                                       "top_p": settings.ollama_top_p,
                                       "top_k": settings.ollama_top_k,
                                       "repeat_penalty": settings.ollama_repeat_penalty},
                              query_prefix=settings.ollama_embedding_query_prefix,
                              passage_prefix=settings.ollama_embedding_passage_prefix,
                              model_resolver=active_model_resolver(settings))
    raise LLMError(f"LLM_PROVIDER inconnu : {settings.llm_provider!r} (fake | demo | ollama)")
