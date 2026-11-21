"""Données de démonstration (07 §9) : déterminisme par graine, marquage, ordre des configurations."""

import pytest
from sqlalchemy import create_engine, text

from app.dw import kpi
from app.dw import schema as dws
from app.dw.demo import generate_demo
from app.storage import schema as sc


def make(tmp_path, name="d.db", **kw):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / name).as_posix()}")
    sc.metadata.create_all(engine)
    return engine, generate_demo(engine, **kw)


def q(engine, sql):
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql))]


@pytest.fixture
def demo(tmp_path):
    return make(tmp_path)


def test_counts_and_naming(demo):
    engine, counts = demo
    assert counts["dossiers"] == 12 and counts["runs"] > 100 and counts["dw_rows"] > 0
    names = q(engine, "SELECT name, is_demo FROM dossiers")
    assert len(names) == 12 and all(n["name"].startswith("[DÉMO] ") and n["is_demo"] for n in names)
    assert {r["role"] for r in q(engine, "SELECT role FROM users")} <= {"consultant", "admin"}


def test_is_demo_everywhere_in_dw(demo):
    engine, _ = demo
    checked = 0
    for table in dws.dw_metadata.tables.values():
        if "is_demo" in table.c:
            row = q(engine, f"SELECT COUNT(*) AS n, SUM(CASE WHEN is_demo THEN 1 ELSE 0 END) AS d "
                            f"FROM {table.name}")[0]
            assert row["n"] > 0 and row["n"] == row["d"], table.name
            checked += 1
    assert checked >= 8
    assert all(r["is_demo"] for r in q(engine, "SELECT is_demo FROM v_generation"))


def test_same_seed_same_kpis_other_seed_differs(tmp_path):
    def kpis(engine):
        gens = q(engine, "SELECT * FROM v_generation")
        out = q(engine, "SELECT * FROM v_outcome")
        return (len(gens), kpi.tpv(gens), kpi.citations_valid_rate(gens),
                kpi.number_fidelity(gens), kpi.refusal_rate(gens), kpi.unchanged_rate(out),
                kpi.mean_edit_ratio(out), kpi.minutes_saved(out))

    a, _ = make(tmp_path, "a.db", seed=7)
    b, _ = make(tmp_path, "b.db", seed=7)
    c, _ = make(tmp_path, "c.db", seed=8)
    ka, kb, kc = kpis(a), kpis(b), kpis(c)
    assert ka == pytest.approx(kb, abs=1e-9)
    assert ka != pytest.approx(kc, abs=1e-6)


def test_config_order_c_b_d_a(demo):
    engine, _ = demo
    by = {r["config_label"]: r["tpv"] for r in q(engine, "SELECT config_label, tpv FROM v_quality_by_model")}
    assert set(by) == {"A", "B", "C", "D"}
    assert by["C"] > by["B"] > by["D"] > by["A"]
    assert by["A"] == pytest.approx(0.35, abs=0.1) and by["B"] == pytest.approx(0.82, abs=0.06)


def test_distributions_plausible(demo):
    engine, _ = demo
    out = q(engine, "SELECT * FROM v_outcome")
    assert 0.1 < kpi.mean_edit_ratio(out) < 0.4 and 0.1 < kpi.unchanged_rate(out) < 0.6
    funnel = q(engine, "SELECT * FROM v_review_funnel")
    assert any(f["rejections"] for f in funnel) and any(f["approved_date_key"] for f in funnel)
    assert q(engine, "SELECT COUNT(*) AS n FROM v_security WHERE injection_alert_count > 0")[0]["n"] > 0
    assert {c["issue_code"] for c in q(engine, "SELECT issue_code FROM v_citations")} >= {"NONE"}


def test_second_call_is_noop(demo):
    engine, _ = demo
    again = generate_demo(engine)
    assert again["dossiers"] == 0 and sum(again.values()) == 0
    assert q(engine, "SELECT COUNT(*) AS n FROM dossiers")[0]["n"] == 12
