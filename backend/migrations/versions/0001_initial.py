"""Schéma initial (06 §4.2) + extension pgvector + index HNSW (PostgreSQL seulement).

Révision : 0001
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Tables propres à ce lot, dans l'ordre de dépendance (gelées : ne pas dépendre de `metadata`).
_TABLES = [
    "users", "sessions", "dossiers", "dossier_members", "documents", "chunks",
    "injection_alerts", "findings", "deliverables", "deliverable_versions",
    "section_comments", "state_transitions", "generation_runs", "retrieval_hits",
    "verification_results", "exports", "audit_log",
]


def upgrade() -> None:
    from app.storage.schema import metadata

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    metadata.create_all(bind, tables=[metadata.tables[t] for t in _TABLES])
    if bind.dialect.name == "postgresql":
        op.execute("CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
                   "USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    from app.storage.schema import metadata

    bind = op.get_bind()
    metadata.drop_all(bind, tables=[metadata.tables[t] for t in _TABLES])
