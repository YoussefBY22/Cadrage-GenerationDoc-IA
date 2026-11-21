"""Configuration : tout vient de l'environnement (jamais de secret dans le dépôt)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "fake" (tests, démo sans GPU) ou "ollama" (réel, sur la machine du client)
    llm_provider: str = "fake"
    ollama_base_url: str = "http://localhost:11434"
    ollama_generation_model: str = ""   # ex. nom du modèle installé par l'utilisateur
    ollama_embedding_model: str = ""
    llm_timeout_seconds: float = 120.0
    # Garde-fou : le serveur de modèle doit être local ou dans cette liste (séparée par des virgules)
    llm_allowed_hosts: str = "localhost,127.0.0.1,::1,ollama,host.docker.internal"

    database_url: str = ""   # vide = base non configurée (tests sans base)
    log_level: str = "INFO"

    @property
    def allowed_hosts(self) -> set[str]:
        return {h.strip() for h in self.llm_allowed_hosts.split(",") if h.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
