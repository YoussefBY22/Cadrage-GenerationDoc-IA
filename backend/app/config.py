"""Configuration : tout vient de l'environnement (jamais de secret dans le dépôt)."""

from functools import lru_cache
from typing import Literal

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

    # Stockage et recherche (06 §11)
    storage_url: str = "sqlite+pysqlite:///./data/app.db"
    embedding_dim: int = 64
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 25
    allow_self_approval: bool = False
    retrieval_k: int = 10
    retrieval_pool: int = 50
    rrf_k: int = 60
    support_threshold: float = 0.3
    session_ttl_hours: int = 12
    soffice_path: str = "soffice"
    auth_mode: Literal["dev", "token"] = "token"
    # Origines autorisées à appeler l'API depuis un navigateur (front en développement sur :3000).
    # Vide = aucune (déploiement même origine derrière le proxy).
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_hosts(self) -> set[str]:
        return {h.strip() for h in self.llm_allowed_hosts.split(",") if h.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
