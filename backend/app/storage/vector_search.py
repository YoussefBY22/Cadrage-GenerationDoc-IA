"""Recherche vectorielle : force brute (SQLite) ou opérateur `<=>` de pgvector (PostgreSQL)."""

import math
from typing import Protocol

from sqlalchemy import Engine, select, text

from .schema import chunks


class VectorSearch(Protocol):
    def search(self, dossier_id: str, query: list[float], k: int,
               document_ids: list[str] | None = None) -> list[tuple[str, float]]: ...


def cosine(a: list[float], b: list[float]) -> float:
    """Similarité cosinus ; 0.0 si l'un des vecteurs est nul."""
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=False)) / (na * nb)


class BruteForceVectorSearch:
    """Charge les vecteurs du seul dossier demandé ; acceptable < 50 000 passages."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def search(self, dossier_id, query, k, document_ids=None):
        stmt = select(chunks.c.id, chunks.c.embedding).where(
            chunks.c.dossier_id == dossier_id, chunks.c.embedding.is_not(None))
        if document_ids is not None:
            stmt = stmt.where(chunks.c.document_id.in_(document_ids))
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).all()
        scored = [(cid, cosine(query, emb)) for cid, emb in rows]
        scored.sort(key=lambda t: (-t[1], t[0]))
        return scored[:k]


class PgVectorSearch:
    """Distance cosinus pgvector (`<=>`), servie par l'index HNSW."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def search(self, dossier_id, query, k, document_ids=None):
        sql = ("SELECT id, 1 - (embedding <=> CAST(:q AS vector)) AS sim FROM chunks "
               "WHERE dossier_id = :d AND embedding IS NOT NULL")
        params: dict = {"q": "[" + ",".join(repr(float(x)) for x in query) + "]",
                        "d": dossier_id, "k": k}
        if document_ids is not None:
            sql += " AND document_id = ANY(:docs)"
            params["docs"] = list(document_ids)
        sql += " ORDER BY embedding <=> CAST(:q AS vector), id LIMIT :k"
        with self.engine.connect() as conn:
            return [(r[0], float(r[1])) for r in conn.execute(text(sql), params)]


def build_vector_search(engine: Engine) -> VectorSearch:
    """Choisit l'implémentation selon le dialecte."""
    if engine.dialect.name == "postgresql":
        return PgVectorSearch(engine)
    return BruteForceVectorSearch(engine)
