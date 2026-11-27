"""Vues SQL portables (07 §4) et cohérence vues ↔ kpi.py à 1e-9 (07 §11 point 4)."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.dw import kpi
from app.dw.etl import DEFAULT_BASELINE_MINUTES, run_etl
from app.dw.views_sql import VIEWS, create_views, drop_views
from app.storage import schema as sc

from . import build_operational

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def loaded(repo):
    build_operational(repo)
    run_etl(repo.engine, repo.engine)
    create_views(repo.engine)
    return repo


def rows(repo, sql):
    with repo.engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql))]


def test_views_exist_and_are_idempotent(loaded):
    assert len(VIEWS) == 22
    create_views(loaded.engine)
    assert set(VIEWS) <= set(inspect(loaded.engine).get_view_names())
    for v in VIEWS:
        rows(loaded, f"SELECT * FROM {v}")


def test_v_generation_row_per_run(loaded):
    r = rows(loaded, "SELECT * FROM v_generation ORDER BY run_id")
    assert len(r) == 5
    run1 = r[0]
    assert run1["tpv"] == pytest.approx(0.5) and run1["client_name"] == "Acme SA"
    assert run1["type_code"] == "tor" and run1["section_code"] == "contexte"
    assert run1["month"] == 9 and run1["config_label"] == "B"
    assert next(x for x in r if x["run_id"] == "run_3")["tpv"] is None


def test_views_match_kpi(loaded):
    gens = rows(loaded, "SELECT * FROM v_generation")
    out = rows(loaded, "SELECT * FROM v_outcome")
    calls = rows(loaded, "SELECT * FROM v_llm_calls")
    tot = rows(loaded, """
        SELECT 1.0 * SUM(CASE WHEN status='ok' THEN sentences_verified ELSE 0 END)
               / SUM(CASE WHEN status='ok' THEN sentences_total ELSE 0 END) AS tpv,
               1.0 * SUM(citations_valid) / SUM(citations_total) AS cv,
               1.0 * SUM(numbers_found) / SUM(numbers_cited) AS nf
        FROM v_generation""")[0]
    assert tot["tpv"] == pytest.approx(kpi.tpv(gens), abs=1e-9) == pytest.approx(0.5, abs=1e-9)
    assert tot["cv"] == pytest.approx(kpi.citations_valid_rate(gens), abs=1e-9)
    assert tot["nf"] == pytest.approx(kpi.number_fidelity(gens), abs=1e-9)
    unch = rows(loaded, "SELECT 1.0 * SUM(CASE WHEN unchanged THEN 1 ELSE 0 END) / COUNT(*) AS u,"
                        " AVG(edit_ratio) AS e, SUM(minutes_saved_est) AS m FROM v_outcome")[0]
    assert unch["u"] == pytest.approx(kpi.unchanged_rate(out), abs=1e-9) == 0.5
    assert unch["e"] == pytest.approx(kpi.mean_edit_ratio(out), abs=1e-9)
    assert unch["m"] == pytest.approx(kpi.minutes_saved(out), abs=1e-9)
    assert kpi.minutes_saved(out) == pytest.approx(30 * (1 - 0.125) + 30, abs=0.1)
    tps = rows(loaded, "SELECT SUM(tokens_out) * 1000.0 / SUM(latency_ms) AS t FROM v_llm_calls")[0]
    assert tps["t"] == pytest.approx(kpi.throughput_tokens_per_s(calls), abs=1e-9)


def test_v_outcome_exposes_baseline_minutes(loaded):
    """Dénominateur du « temps gagné » en pourcentage (H7) : le temps manuel de référence."""
    out = rows(loaded, "SELECT * FROM v_outcome")
    assert out
    for o in out:
        assert float(o["baseline_minutes"]) == DEFAULT_BASELINE_MINUTES
        expected = round(float(o["baseline_minutes"]) * (1 - float(o["edit_ratio"])), 1)
        assert float(o["minutes_saved_est"]) == pytest.approx(expected)


def test_quality_by_model_matches_kpi(loaded):
    gens = rows(loaded, "SELECT * FROM v_generation")
    for q in rows(loaded, "SELECT * FROM v_quality_by_model"):
        mine = [g for g in gens if g["model_key"] == q["model_key"]
                and bool(g["is_demo"]) == bool(q["is_demo"])]
        assert q["n_generations"] == len(mine)
        for key, fn in (("tpv", kpi.tpv), ("citations_valid_rate", kpi.citations_valid_rate),
                        ("number_fidelity", kpi.number_fidelity),
                        ("refusal_rate", kpi.refusal_rate), ("invalid_rate", kpi.invalid_rate)):
            expected = fn(mine)
            if expected is None:
                assert q[key] is None
            else:
                assert q[key] == pytest.approx(expected, abs=1e-9)


def test_review_funnel_citations_security_calls(loaded):
    f = {r["deliverable_id"]: r for r in rows(loaded, "SELECT * FROM v_review_funnel")}
    assert len(f) == 2
    done = next(r for r in f.values() if r["approved_date_key"] is not None)
    assert done["submissions"] == 1 and done["rejections"] == 0
    assert done["delay_hours"] == pytest.approx(2.0) and done["submitted_date_key"] == 20260901
    cit = rows(loaded, "SELECT issue_code, COUNT(*) AS n FROM v_citations GROUP BY issue_code")
    assert {r["issue_code"]: r["n"] for r in cit} == {"NONE": 3, "FOREIGN_SOURCE": 1,
                                                     "UNKNOWN_SOURCE": 1}
    assert sum(r["injection_alert_count"] for r in rows(loaded, "SELECT * FROM v_security")) == 2
    call = rows(loaded, "SELECT tokens_per_second FROM v_llm_calls WHERE latency_ms = 1000 "
                        "AND tokens_out = 100 LIMIT 1")[0]
    assert call["tokens_per_second"] == pytest.approx(100.0)


def test_drop_views(loaded):
    drop_views(loaded.engine)
    assert inspect(loaded.engine).get_view_names() == []


def test_alembic_0002_creates_dw_and_views(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'm.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.cmd_opts = SimpleNamespace(x=[f"url={url}"])
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    assert {"fact_review", "dim_date", "etl_watermark"} <= set(insp.get_table_names())
    assert set(VIEWS) <= set(insp.get_view_names())
    assert set(sc.metadata.tables) <= set(insp.get_table_names())
    command.downgrade(cfg, "0001")
    insp = inspect(create_engine(url))
    assert "fact_review" not in insp.get_table_names() and insp.get_view_names() == []
