import pytest

from . import netguard


@pytest.fixture(autouse=True)
def _no_outbound_network():
    """Appliqué à TOUS les tests : le réseau externe est coupé."""
    uninstall = netguard.install()
    yield
    uninstall()


# --- B1 : stockage -------------------------------------------------------------------------
@pytest.fixture
def sqlite_url(tmp_path):
    return f"sqlite+pysqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def repo(sqlite_url):
    from app.config import Settings
    from app.storage import build_repository

    return build_repository(Settings(storage_url=sqlite_url, auth_mode="dev"))


@pytest.fixture
def provider():
    from app.llm import FakeProvider

    return FakeProvider()


@pytest.fixture
def client(provider, repo, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    with TestClient(create_app(provider, repo)) as c:
        yield c
    get_settings.cache_clear()
