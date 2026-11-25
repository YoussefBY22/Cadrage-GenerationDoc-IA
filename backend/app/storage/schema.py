"""Schéma opérationnel (06 §4.2) : SQLAlchemy 2 Core, une seule `MetaData`."""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from ..config import get_settings
from .types import EmbeddingType, JsonType

metadata = MetaData()
ID = String(32)


def utcnow() -> datetime:
    return datetime.now(UTC)


def _dt(name: str, **kw) -> Column:
    return Column(name, DateTime(timezone=True), **kw)


users = Table(
    "users", metadata,
    Column("id", ID, primary_key=True),
    Column("email", String(255), nullable=False, unique=True),
    Column("display_name", String(255), nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("role", String(16), nullable=False),
    _dt("created_at", nullable=False, default=utcnow),
    Column("active", Boolean, nullable=False, default=True),
)

sessions = Table(
    "sessions", metadata,
    Column("token_hash", String(128), primary_key=True),
    Column("user_id", ID, ForeignKey("users.id"), nullable=False),
    _dt("expires_at", nullable=False),
)

dossiers = Table(
    "dossiers", metadata,
    Column("id", ID, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("client_name", String(255), nullable=False),
    Column("sector", String(128)),
    Column("language", String(2), nullable=False),
    Column("owner_id", ID, ForeignKey("users.id"), nullable=False),
    _dt("created_at", nullable=False, default=utcnow),
    Column("archived", Boolean, nullable=False, default=False),
    Column("is_demo", Boolean, nullable=False, default=False),
)

dossier_members = Table(
    "dossier_members", metadata,
    Column("dossier_id", ID, ForeignKey("dossiers.id"), primary_key=True),
    Column("user_id", ID, ForeignKey("users.id"), primary_key=True),
    Column("role", String(16), nullable=False),
)

documents = Table(
    "documents", metadata,
    Column("id", ID, primary_key=True),
    Column("dossier_id", ID, ForeignKey("dossiers.id"), nullable=False),
    Column("filename", String(512), nullable=False),
    Column("mime", String(128), nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("title", Text),
    Column("language", String(2)),
    Column("pages", Integer),
    Column("stored_path", Text, nullable=False),
    _dt("created_at", nullable=False, default=utcnow),
    Column("created_by", ID),
    Column("role", String(16), nullable=False, default="other", server_default="other"),
    UniqueConstraint("dossier_id", "sha256", name="uq_documents_dossier_sha"),
)

chunks = Table(
    "chunks", metadata,
    Column("id", ID, primary_key=True),
    Column("document_id", ID, ForeignKey("documents.id"), nullable=False),
    Column("dossier_id", ID, ForeignKey("dossiers.id"), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("page_start", Integer),
    Column("page_end", Integer),
    Column("section_path", JsonType(), nullable=False),
    Column("token_estimate", Integer, nullable=False),
    Column("injection_flags", JsonType(), nullable=False),
    Column("embedding", EmbeddingType(get_settings().embedding_dim)),
    Column("embedding_model", String(128)),
    Index("ix_chunks_dossier", "dossier_id"),
)

injection_alerts = Table(
    "injection_alerts", metadata,
    Column("id", ID, primary_key=True),
    Column("chunk_id", ID, ForeignKey("chunks.id"), nullable=False),
    Column("dossier_id", ID, nullable=False),
    Column("codes", JsonType(), nullable=False),
    _dt("created_at", nullable=False, default=utcnow),
)

findings = Table(
    "findings", metadata,
    Column("id", ID, primary_key=True),
    Column("dossier_id", ID, ForeignKey("dossiers.id"), nullable=False),
    Column("text", Text, nullable=False),
    Column("theme", String(128), nullable=False),
    Column("severity", String(8), nullable=False),
    Column("source_ids", JsonType(), nullable=False),
    Column("validated", Boolean, nullable=False, default=False),
    Column("validated_by", ID),
    Column("created_run_id", ID),
)

deliverables = Table(
    "deliverables", metadata,
    Column("id", ID, primary_key=True),
    Column("dossier_id", ID, ForeignKey("dossiers.id"), nullable=False),
    Column("type", String(16), nullable=False),
    Column("template_id", String(64), nullable=False),
    Column("state", String(16), nullable=False, default="draft"),
    Column("current_version", Integer, nullable=False, default=0),
    Column("author_id", ID, nullable=False),
    _dt("created_at", nullable=False, default=utcnow),
    _dt("updated_at", nullable=False, default=utcnow),
)

deliverable_versions = Table(
    "deliverable_versions", metadata,
    Column("deliverable_id", ID, ForeignKey("deliverables.id"), primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("content", JsonType(), nullable=False),
    Column("origin", String(16), nullable=False),
    Column("author_id", ID, nullable=False),
    _dt("created_at", nullable=False, default=utcnow),
    Column("content_sha256", String(64), nullable=False),
)

section_comments = Table(
    "section_comments", metadata,
    Column("id", ID, primary_key=True),
    Column("deliverable_id", ID, ForeignKey("deliverables.id"), nullable=False),
    Column("section_key", String(128), nullable=False),
    Column("user_id", ID, nullable=False),
    Column("text", Text, nullable=False),
    _dt("created_at", nullable=False, default=utcnow),
)

state_transitions = Table(
    "state_transitions", metadata,
    Column("id", ID, primary_key=True),
    Column("deliverable_id", ID, ForeignKey("deliverables.id"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("from_state", String(16), nullable=False),
    Column("to_state", String(16), nullable=False),
    Column("user_id", ID, nullable=False),
    Column("reason", Text),
    _dt("at", nullable=False, default=utcnow),
)

generation_runs = Table(
    "generation_runs", metadata,
    Column("id", ID, primary_key=True),
    Column("dossier_id", ID, nullable=False),
    Column("deliverable_id", ID),
    Column("section_key", String(128)),
    Column("kind", String(16), nullable=False),
    Column("provider", String(64)),
    Column("model", String(128)),
    Column("adapter", String(128)),
    Column("config_label", String(64)),
    Column("params", JsonType()),
    Column("prompt_sha256", String(64)),
    Column("status", String(16), nullable=False),
    Column("attempts", Integer, nullable=False, default=1),
    Column("latency_ms", Integer),
    Column("tokens_in", Integer),
    Column("tokens_out", Integer),
    _dt("started_at", nullable=False, default=utcnow),
)

retrieval_hits = Table(
    "retrieval_hits", metadata,
    Column("run_id", ID, ForeignKey("generation_runs.id"), primary_key=True),
    Column("label", String(8), primary_key=True),
    Column("chunk_id", ID, nullable=False),
    Column("rank", Integer, nullable=False),
    Column("score", Float, nullable=False),
    Column("bm25_rank", Integer),
    Column("vector_rank", Integer),
)

verification_results = Table(
    "verification_results", metadata,
    Column("run_id", ID, ForeignKey("generation_runs.id"), primary_key=True),
    Column("sentence_index", Integer, primary_key=True),
    Column("status", String(16), nullable=False),
    Column("numbers_cited", Integer, nullable=False),
    Column("numbers_found", Integer, nullable=False),
    Column("support", Float, nullable=False),
    Column("issues", JsonType(), nullable=False),
)

exports = Table(
    "exports", metadata,
    Column("id", ID, primary_key=True),
    Column("deliverable_id", ID, ForeignKey("deliverables.id"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("format", String(8), nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("path", Text, nullable=False),
    Column("user_id", ID, nullable=False),
    _dt("at", nullable=False, default=utcnow),
)

audit_log = Table(
    "audit_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    _dt("at", nullable=False, default=utcnow),
    Column("user_id", ID),
    Column("action", String(64), nullable=False),
    Column("object_type", String(64), nullable=False),
    Column("object_id", String(64), nullable=False),
    Column("details", JsonType(), nullable=False),
)

priorities = Table(
    "priorities", metadata,
    Column("id", ID, primary_key=True),
    Column("dossier_id", ID, ForeignKey("dossiers.id"), nullable=False),
    Column("title", Text, nullable=False),
    Column("description", Text, nullable=False, default=""),
    Column("rank", Integer, nullable=False),
    Column("status", String(16), nullable=False, default="proposed"),
    Column("source_ids", JsonType(), nullable=False),
    Column("author_id", ID),
    Column("validated_by", ID),
    _dt("validated_at"),
    _dt("created_at", nullable=False, default=utcnow),
    _dt("updated_at", nullable=False, default=utcnow),
    Index("ix_priorities_dossier", "dossier_id"),
)

existing_projects = Table(
    "existing_projects", metadata,
    Column("id", ID, primary_key=True),
    Column("dossier_id", ID, ForeignKey("dossiers.id"), nullable=False),
    Column("title", Text, nullable=False),
    Column("state", String(16), nullable=False, default="existing"),
    Column("duration_weeks", Integer),
    Column("depends_on", JsonType(), nullable=False),
    Column("source_ids", JsonType(), nullable=False),
    Column("author_id", ID),
    _dt("created_at", nullable=False, default=utcnow),
    _dt("updated_at", nullable=False, default=utcnow),
    Index("ix_existing_projects_dossier", "dossier_id"),
)

decisions = Table(
    "decisions", metadata,
    Column("id", ID, primary_key=True),
    Column("dossier_id", ID, ForeignKey("dossiers.id"), nullable=False),
    Column("category", String(16), nullable=False),
    Column("text", Text, nullable=False),
    Column("status", String(16), nullable=False, default="proposed"),
    Column("author_id", ID),
    Column("confirmed_by", ID),
    _dt("confirmed_at"),
    _dt("created_at", nullable=False, default=utcnow),
    _dt("updated_at", nullable=False, default=utcnow),
    Index("ix_decisions_dossier", "dossier_id"),
)

# Fiche de contexte : une ligne par dossier ; seules les valeurs confirmées par un humain y entrent.
context_sheets = Table(
    "context_sheets", metadata,
    Column("dossier_id", ID, ForeignKey("dossiers.id"), primary_key=True),
    Column("data", JsonType(), nullable=False),
    Column("confirmed_by", ID),
    _dt("confirmed_at"),
    Column("updated_by", ID),
    _dt("updated_at", nullable=False, default=utcnow),
)

# --- Fiche projet, recommandations des rapports, registre des entraînements -------------------
# Tables ajoutées sans modifier les précédentes : `create_all` suffit sur une base existante.
dossier_profiles = Table(
    "dossier_profiles", metadata,
    Column("dossier_id", ID, ForeignKey("dossiers.id"), primary_key=True),
    Column("client_request", Text, nullable=False, default=""),  # demande du client, complète
    Column("request_summary", String(200), nullable=False, default=""),  # seul texte copié dans l'entrepôt
    Column("start_date", String(10)),  # ISO aaaa-mm-jj
    Column("end_date", String(10)),
    Column("logo", Text),  # data URI PNG, redimensionné à l'envoi (≈ 100 Ko au plus)
    Column("updated_by", ID),
    _dt("updated_at", nullable=False, default=utcnow),
)

# Ce que le rapport annonce : numéros « Recommandation n° … » relevés dans le texte, à chaque extraction.
report_checks = Table(
    "report_checks", metadata,
    Column("document_id", ID, ForeignKey("documents.id"), primary_key=True),
    Column("dossier_id", ID, ForeignKey("dossiers.id"), nullable=False),
    Column("numbers_seen", JsonType(), nullable=False),  # numéros cités, triés
    Column("no_recommendation", Boolean, nullable=False, default=False),  # confirmé par le consultant
    _dt("checked_at", nullable=False, default=utcnow),
)

audit_recommendations = Table(
    "audit_recommendations", metadata,
    Column("id", ID, primary_key=True),
    Column("dossier_id", ID, ForeignKey("dossiers.id"), nullable=False),
    Column("document_id", ID, ForeignKey("documents.id"), nullable=False),
    Column("number", Integer),  # numéro dans le rapport ; NULL si le rapport ne numérote pas
    Column("page", Integer),
    Column("title", Text, nullable=False),
    Column("status", String(12), nullable=False, default="proposed"),  # proposed|validated|deleted|merged
    Column("origin", String(12), nullable=False, default="rules"),  # rules|consultant
    Column("merged_into", ID),
    Column("chunk_id", ID),
    Column("updated_by", ID),
    _dt("created_at", nullable=False, default=utcnow),
    _dt("updated_at", nullable=False, default=utcnow),
    Index("ix_audit_recommendations_dossier", "dossier_id"),
)

training_runs = Table(
    "training_runs", metadata,
    Column("id", String(40), primary_key=True),  # nom court, ex. « v4 »
    Column("label", String(80), nullable=False),
    Column("run_date", String(10), nullable=False),
    Column("platform", String(40), nullable=False),
    Column("gpu", String(40)),
    Column("examples", Integer, nullable=False),
    Column("test_examples", Integer),
    Column("duration_min", Float),
    Column("steps_planned", Integer),
    Column("stop_step", Integer),
    Column("best_step", Integer),
    Column("best_val_loss", Float),
    Column("adopted", Boolean, nullable=False, default=False),
    Column("outcome", String(200), nullable=False, default=""),
    _dt("imported_at", nullable=False, default=utcnow),
)

training_eval_points = Table(
    "training_eval_points", metadata,
    Column("run_id", String(40), ForeignKey("training_runs.id"), primary_key=True),
    Column("step", Integer, primary_key=True),
    Column("val_loss", Float, nullable=False),
)

training_task_scores = Table(
    "training_task_scores", metadata,
    Column("run_id", String(40), ForeignKey("training_runs.id"), primary_key=True),
    Column("model", String(20), primary_key=True),  # base | modèle entraîné
    Column("task", String(40), primary_key=True),
    Column("correct", Integer, nullable=False),
    Column("total", Integer, nullable=False),
)
