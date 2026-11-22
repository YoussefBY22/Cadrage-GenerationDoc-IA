"""Configuration : tout vient de l'environnement (jamais de secret dans le dépôt)."""

import os
import shutil
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_soffice(value: str) -> str:
    """« soffice » n'est pas dans le PATH après une installation Windows : chercher l'emplacement standard."""
    if value != "soffice" or shutil.which(value) or os.name != "nt":
        return value
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if base:
            candidate = os.path.join(base, "LibreOffice", "program", "soffice.exe")
            if os.path.isfile(candidate):
                return candidate
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "fake" (tests, démo sans GPU) ou "ollama" (réel, sur la machine du client)
    llm_provider: str = "fake"
    ollama_base_url: str = "http://localhost:11434"
    ollama_generation_model: str = ""   # ex. nom du modèle installé par l'utilisateur
    ollama_embedding_model: str = ""
    llm_timeout_seconds: float = 120.0
    # Réglages du modèle réel (T2) ; None = valeur par défaut d'Ollama
    ollama_think: bool = False           # Qwen3 : réflexion désactivée
    ollama_keep_alive: str = "30m"
    ollama_temperature: float | None = None   # None = celle demandée par l'appelant (0.0)
    ollama_num_ctx: int | None = None
    ollama_num_gpu: int | None = None         # 99 = toutes les couches sur le GPU (x2 en vitesse sur 4 Go)
    ollama_num_predict: int | None = None
    ollama_top_p: float | None = None
    ollama_top_k: int | None = None
    ollama_repeat_penalty: float | None = None
    ollama_embedding_query_prefix: str = ""     # bge-m3 : aucun préfixe (e5 : "query: ")
    ollama_embedding_passage_prefix: str = ""   # e5 : "passage: "
    # Garde-fou : le serveur de modèle doit être local ou dans cette liste (séparée par des virgules)
    llm_allowed_hosts: str = "localhost,127.0.0.1,::1,ollama,host.docker.internal"

    database_url: str = ""   # vide = base non configurée (tests sans base)
    log_level: str = "INFO"

    # Stockage et recherche (06 §11)
    storage_url: str = "sqlite+pysqlite:///./data/app.db"
    embedding_dim: int = 64          # bge-m3 : 1024 (ré-indexer si on change de modèle)
    embedding_passage_prefix: str = "passage: "   # bge-m3 : "" (e5 : "passage: ")
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 25
    allow_self_approval: bool = False
    retrieval_k: int = 10
    retrieval_pool: int = 50
    rrf_k: int = 60
    support_threshold: float = 0.3
    session_ttl_hours: int = 12
    soffice_path: str = "soffice"   # sous Windows, repli automatique sur Program Files\LibreOffice
    auth_mode: Literal["dev", "token"] = "token"
    # Origines autorisées à appeler l'API depuis un navigateur (front en développement sur :3000).
    # Vide = aucune (déploiement même origine derrière le proxy).
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @field_validator("soffice_path")
    @classmethod
    def _soffice_windows(cls, v: str) -> str:
        return _find_soffice(v)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_hosts(self) -> set[str]:
        return {h.strip() for h in self.llm_allowed_hosts.split(",") if h.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
