"""Environnement Alembic : l'URL vient de `-x url=…` ou des réglages (`storage_url`)."""

from alembic import context
from sqlalchemy import create_engine

from app.config import get_settings
from app.storage.schema import metadata

config = context.config


def _url() -> str:
    return context.get_x_argument(as_dictionary=True).get("url") or get_settings().storage_url


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
