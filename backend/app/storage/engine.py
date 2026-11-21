"""Moteur SQLAlchemy et construction du dépôt à partir des réglages."""

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool

DEV_USER_ID = "usr_dev"


def make_engine(url: str) -> Engine:
    """Crée le moteur ; SQLite : clés étrangères actives, dossier du fichier créé."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(url, pool_pre_ping=True)
    kwargs: dict = {}
    if parsed.database in (None, "", ":memory:"):
        kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    else:
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def build_repository(settings):
    """Dépôt SQL prêt à l'emploi. SQLite : tables créées ; PostgreSQL : voir Alembic."""
    from .schema import metadata
    from .sql_repository import SqlRepository

    engine = make_engine(settings.storage_url)
    if engine.dialect.name == "sqlite":
        metadata.create_all(engine)
    repo = SqlRepository(engine)
    if settings.auth_mode == "dev":
        repo.ensure_user(DEV_USER_ID, "dev@local", "Utilisateur local", "!", "admin")
    return repo
