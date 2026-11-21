"""Schéma « dw » (07 §2) : modèle en étoile en SQLAlchemy Core.

Sur PostgreSQL, les tables vivent dans le schéma `dw`. Sur SQLite, `schema_translate_map`
supprime le préfixe : les mêmes tables existent à côté des tables opérationnelles.
Aucun texte libre du client : toutes les colonnes texte font au plus 200 caractères.
"""

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    UniqueConstraint,
    text,
)

SCHEMA = "dw"
dw_metadata = MetaData(schema=SCHEMA)

_BigPk = BigInteger().with_variant(Integer, "sqlite")  # auto-incrément SQLite


def _num(p: int, s: int) -> Numeric:
    return Numeric(p, s, asdecimal=False)


def _t(name: str, *cols, **kw) -> Table:
    return Table(name, dw_metadata, *cols, **kw)


def _fk(target: str) -> ForeignKey:
    return ForeignKey(f"{SCHEMA}.{target}")


def _demo() -> Column:
    return Column("is_demo", Boolean, nullable=False, default=False)


# --- Dimensions ------------------------------------------------------------------------------
dim_date = _t(
    "dim_date",
    Column("date_key", Integer, primary_key=True, autoincrement=False),
    Column("date", String(10), nullable=False),  # ISO aaaa-mm-jj (portable)
    Column("year", SmallInteger, nullable=False),
    Column("quarter", SmallInteger, nullable=False),
    Column("month", SmallInteger, nullable=False),
    Column("month_name_fr", String(12), nullable=False),
    Column("iso_week", SmallInteger, nullable=False),
    Column("day_of_week", SmallInteger, nullable=False),
    Column("is_weekend", Boolean, nullable=False),
)

dim_client = _t(
    "dim_client",
    Column("client_key", Integer, primary_key=True),
    Column("client_ref", String(64), nullable=False, unique=True),  # sha256 du nom (clé naturelle)
    Column("client_name", String(200), nullable=False),
    Column("sector", String(80)),
    _demo(),
)

dim_mission = _t(
    "dim_mission",
    Column("mission_key", Integer, primary_key=True),
    Column("dossier_id", String(32), nullable=False, unique=True),
    Column("client_key", Integer, _fk("dim_client.client_key"), nullable=False),
    Column("mission_name", String(200), nullable=False),
    Column("language", String(2), nullable=False),
    Column("created_date_key", Integer),
    _demo(),
)

dim_document = _t(
    "dim_document",
    Column("document_key", Integer, primary_key=True),
    Column("document_id", String(32), nullable=False, unique=True),
    Column("mission_key", Integer, _fk("dim_mission.mission_key"), nullable=False),
    Column("mime", String(80), nullable=False),
    Column("pages", Integer),
    Column("chunk_count", Integer, nullable=False, default=0),
    Column("injection_alert_count", Integer, nullable=False, default=0),
    _demo(),
)

dim_user = _t(
    "dim_user",
    Column("user_key", Integer, primary_key=True),
    Column("user_id", String(32), nullable=False, unique=True),
    Column("role", String(20), nullable=False),
    Column("user_label", String(80), nullable=False),
    _demo(),
)

dim_model = _t(
    "dim_model",
    Column("model_key", Integer, primary_key=True),
    Column("provider", String(40), nullable=False),
    Column("model_name", String(120), nullable=False),
    Column("adapter", String(120)),
    Column("quantization", String(20)),
    Column("config_label", String(1)),
    _demo(),
    UniqueConstraint("provider", "model_name", "adapter", "config_label", "is_demo",
                     name="uq_dim_model"),
)

dim_deliverable_type = _t(
    "dim_deliverable_type",
    Column("type_key", SmallInteger, primary_key=True, autoincrement=False),
    Column("type_code", String(12), nullable=False, unique=True),
    Column("label_fr", String(60), nullable=False),
    Column("label_en", String(60), nullable=False),
)

dim_section = _t(
    "dim_section",
    Column("section_key", Integer, primary_key=True),
    Column("type_key", SmallInteger, _fk("dim_deliverable_type.type_key"), nullable=False),
    Column("template_id", String(60), nullable=False),
    Column("section_code", String(60), nullable=False),
    Column("title_fr", String(200), nullable=False),
    Column("baseline_minutes", _num(6, 1), nullable=False),
    UniqueConstraint("template_id", "section_code", name="uq_dim_section"),
)

dim_issue = _t(
    "dim_issue",
    Column("issue_key", SmallInteger, primary_key=True, autoincrement=False),
    Column("issue_code", String(30), nullable=False, unique=True),
    Column("severity", String(10), nullable=False),
    Column("label_fr", String(120), nullable=False),
)

dim_state = _t(
    "dim_state",
    Column("state_key", SmallInteger, primary_key=True, autoincrement=False),
    Column("state_code", String(12), nullable=False, unique=True),
    Column("label_fr", String(30), nullable=False),
    Column("step_order", SmallInteger, nullable=False),
)

# --- Faits -----------------------------------------------------------------------------------
fact_section_generation = _t(
    "fact_section_generation",
    Column("generation_key", _BigPk, primary_key=True),
    Column("run_id", String(32), nullable=False, unique=True),
    Column("date_key", Integer, _fk("dim_date.date_key"), nullable=False),
    Column("mission_key", Integer, _fk("dim_mission.mission_key"), nullable=False),
    Column("model_key", Integer, _fk("dim_model.model_key"), nullable=False),
    Column("section_key", Integer, _fk("dim_section.section_key"), nullable=False),
    Column("user_key", Integer, _fk("dim_user.user_key"), nullable=False),
    Column("status", String(12), nullable=False),
    Column("sentences_total", Integer, nullable=False, default=0),
    Column("sentences_verified", Integer, nullable=False, default=0),
    Column("sentences_warning", Integer, nullable=False, default=0),
    Column("sentences_failed", Integer, nullable=False, default=0),
    Column("citations_total", Integer, nullable=False, default=0),
    Column("citations_valid", Integer, nullable=False, default=0),
    Column("numbers_cited", Integer, nullable=False, default=0),
    Column("numbers_found", Integer, nullable=False, default=0),
    Column("passages_retrieved", Integer, nullable=False, default=0),
    Column("attempts", SmallInteger, nullable=False, default=1),
    Column("latency_ms", Integer),
    Column("tokens_in", Integer),
    Column("tokens_out", Integer),
    _demo(),
)

fact_citation_check = _t(
    "fact_citation_check",
    Column("citation_key", _BigPk, primary_key=True),
    Column("generation_key", BigInteger, _fk("fact_section_generation.generation_key"),
           nullable=False),
    Column("document_key", Integer, _fk("dim_document.document_key")),
    Column("issue_key", SmallInteger, _fk("dim_issue.issue_key"), nullable=False),
    Column("sentence_index", SmallInteger, nullable=False),
    Column("is_valid", Boolean, nullable=False),
    Column("support", _num(4, 3), nullable=False),
    _demo(),
)

fact_llm_call = _t(
    "fact_llm_call",
    Column("call_key", _BigPk, primary_key=True),
    Column("date_key", Integer, _fk("dim_date.date_key"), nullable=False),
    Column("model_key", Integer, _fk("dim_model.model_key"), nullable=False),
    Column("mission_key", Integer, _fk("dim_mission.mission_key"), nullable=False),
    Column("call_kind", String(12), nullable=False),
    Column("latency_ms", Integer),
    Column("tokens_in", Integer),
    Column("tokens_out", Integer),
    Column("success", Boolean, nullable=False),
    _demo(),
)

fact_review = _t(
    "fact_review",
    Column("review_key", _BigPk, primary_key=True),
    Column("transition_id", String(32), nullable=False, unique=True),
    Column("deliverable_id", String(32), nullable=False),
    Column("date_key", Integer, _fk("dim_date.date_key"), nullable=False),
    Column("mission_key", Integer, _fk("dim_mission.mission_key"), nullable=False),
    Column("type_key", SmallInteger, _fk("dim_deliverable_type.type_key"), nullable=False),
    Column("user_key", Integer, _fk("dim_user.user_key"), nullable=False),
    Column("from_state_key", SmallInteger, _fk("dim_state.state_key"), nullable=False),
    Column("to_state_key", SmallInteger, _fk("dim_state.state_key"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("hours_since_previous", _num(10, 2), nullable=False, default=0),
    Column("hours_since_submission", _num(10, 2), nullable=False, default=0),
    Column("has_reason", Boolean, nullable=False, default=False),
    _demo(),
)

fact_section_outcome = _t(
    "fact_section_outcome",
    Column("outcome_key", _BigPk, primary_key=True),
    Column("deliverable_id", String(32), nullable=False),
    Column("approved_version", Integer, nullable=False),
    Column("date_key", Integer, _fk("dim_date.date_key"), nullable=False),
    Column("mission_key", Integer, _fk("dim_mission.mission_key"), nullable=False),
    Column("section_key", Integer, _fk("dim_section.section_key"), nullable=False),
    Column("model_key", Integer, _fk("dim_model.model_key"), nullable=False),
    Column("generated_words", Integer, nullable=False),
    Column("final_words", Integer, nullable=False),
    Column("edit_ratio", _num(5, 4), nullable=False),
    Column("unchanged", Boolean, nullable=False),
    Column("was_refused", Boolean, nullable=False),
    Column("minutes_saved_est", _num(7, 1), nullable=False),
    _demo(),
    UniqueConstraint("deliverable_id", "approved_version", "section_key", name="uq_outcome"),
)

# --- Techniques ------------------------------------------------------------------------------
etl_watermark = _t(
    "etl_watermark",
    Column("source_table", String(64), primary_key=True),
    Column("last_value", String(40), nullable=False),
    Column("updated_at", DateTime(timezone=True)),
)

etl_log = _t(
    "etl_log",
    Column("id", Integer, primary_key=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("ended_at", DateTime(timezone=True)),
    Column("rows_by_table", JSON),
    Column("status", String(12), nullable=False),
    Column("error", String(200)),
)


def bind_dw(engine: Engine) -> Engine:
    """Sur SQLite, retire le préfixe de schéma `dw` ; sinon renvoie le moteur tel quel."""
    if engine.dialect.name == "sqlite":
        return engine.execution_options(schema_translate_map={SCHEMA: None})
    return engine


def create_dw(engine: Engine) -> None:
    """Crée le schéma et les tables (idempotent)."""
    if engine.dialect.name == "postgresql":
        with engine.begin() as c:
            c.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    dw_metadata.create_all(bind_dw(engine))
