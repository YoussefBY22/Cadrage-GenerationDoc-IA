"""Moteur, `build_repository`, application avec dépôt injecté, migration Alembic sur SQLite."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import Settings, get_settings
from app.storage import SqlRepository, build_repository
from app.storage.engine import make_engine
from app.storage.schema import metadata

ROOT = Path(__file__).resolve().parents[2]


def test_build_repository_dev_and_token(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'sub' / 'x.db').as_posix()}"
    repo = build_repository(Settings(storage_url=url, auth_mode="dev"))
    assert repo.get_user_by_email("dev@local")["role"] == "admin"
    build_repository(Settings(storage_url=url, auth_mode="dev"))  # idempotent
    tok = build_repository(Settings(storage_url=f"sqlite+pysqlite:///{tmp_path.as_posix()}/t.db",
                                    auth_mode="token"))
    assert tok.get_user_by_email("dev@local") is None


def test_memory_engine_and_pragma():
    eng = make_engine("sqlite+pysqlite:///:memory:")
    with eng.connect() as c:
        assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1
    metadata.create_all(eng)
    assert isinstance(SqlRepository(eng), SqlRepository)


def test_all_tables_present(repo):
    assert len(metadata.tables) == 19
    assert set(inspect(repo.engine).get_table_names()) >= set(metadata.tables)


def test_client_uses_injected_repo(client, repo):
    assert client.app.state.repo is repo
    assert client.get("/health").status_code == 200


def test_lazy_repo_built_from_settings(tmp_path, monkeypatch):
    from app.api.deps import get_repo
    from app.llm import FakeProvider
    from app.main import create_app

    monkeypatch.setenv("STORAGE_URL", f"sqlite+pysqlite:///{tmp_path.as_posix()}/lazy.db")
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    try:
        app = create_app(FakeProvider())
        assert app.state.repo is None
        fake_request = SimpleNamespace(app=app)
        assert get_repo(fake_request).get_user_by_email("dev@local")["id"] == "usr_dev"
        assert app.state.repo is not None
    finally:
        get_settings.cache_clear()


def test_alembic_upgrade_and_downgrade_on_sqlite(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'mig.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.cmd_opts = SimpleNamespace(x=[f"url={url}"])
    command.upgrade(cfg, "head")
    names = set(inspect(create_engine(url)).get_table_names())
    assert set(metadata.tables) <= names and "alembic_version" in names
    command.downgrade(cfg, "base")
    assert set(metadata.tables).isdisjoint(inspect(create_engine(url)).get_table_names())


@pytest.mark.postgres
def test_postgres_pgvector_search():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL absent")
    from app.storage.vector_search import PgVectorSearch, build_vector_search

    eng = create_engine(url)
    assert isinstance(build_vector_search(eng), PgVectorSearch)
    with eng.connect() as c:
        assert c.execute(text("SELECT 1")).scalar() == 1
