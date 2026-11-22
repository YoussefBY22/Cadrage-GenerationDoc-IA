"""Entrepôt sur PostgreSQL réel (lot T1) : démo, vues, rôle `bi_reader`. Sauté sans TEST_POSTGRES_URL."""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.dw.demo import generate_demo
from app.dw.views_sql import VIEWS

pytestmark = pytest.mark.postgres
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def pg():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL absent")
    eng = create_engine(url)
    generate_demo(eng, seed=42)
    yield url, eng
    eng.dispose()


def test_views_filled_on_postgres(pg):
    _, eng = pg
    with eng.connect() as c:
        for v in VIEWS:
            assert c.execute(text(f"SELECT count(*) FROM dw.{v}")).scalar() > 0, v


def test_bi_reader_role_is_read_only_on_dw(pg):
    url, eng = pg
    sql = (ROOT / "db" / "dw" / "roles.sql").read_text(encoding="utf-8")
    with eng.begin() as c:
        c.exec_driver_sql(sql.replace("CHANGER_MOI", "test-bi"))
    reader = create_engine(make_url(url).set(username="bi_reader", password="test-bi"))
    try:
        with reader.connect() as c:
            assert c.execute(text("SELECT count(*) FROM dw.v_generation")).scalar() > 0
        for forbidden in ("SELECT * FROM public.chunks", "SELECT * FROM public.users",
                          "DELETE FROM dw.dim_model"):
            with reader.connect() as c, pytest.raises(DBAPIError):
                c.execute(text(forbidden))
    finally:
        reader.dispose()
