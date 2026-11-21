"""Types de colonnes portables SQLite / PostgreSQL."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB


def JsonType():
    """JSON sur SQLite, JSONB sur PostgreSQL."""
    return JSON().with_variant(JSONB(), "postgresql")


def EmbeddingType(dim: int):
    """pgvector `Vector(dim)` sur PostgreSQL ; liste JSON de flottants sur SQLite."""
    return JSON().with_variant(Vector(dim), "postgresql")
