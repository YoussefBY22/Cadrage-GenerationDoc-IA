"""Stockage : dépôt unique SQLAlchemy 2 Core (SQLite en test, PostgreSQL + pgvector en prod)."""

from .engine import build_repository
from .repository import DuplicateDocumentError, Repository
from .sql_repository import SqlRepository

__all__ = ["DuplicateDocumentError", "Repository", "SqlRepository", "build_repository"]
