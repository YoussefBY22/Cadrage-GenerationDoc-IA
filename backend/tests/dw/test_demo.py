"""Données de démonstration (07 §9) : déterminisme, marquage, fidélité au produit."""

import pytest
from sqlalchemy import create_engine, text

from app.domain.workflow import State
from app.dw import kpi
from app.dw import schema as dws
from app.dw.demo import BENCH, generate_demo
from app.ingest.registry import MIME
from app.storage import schema as sc
from app.workflow.state_machine import ALLOWED


def make(tmp_path, name="d.db", **kw):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / name).as_posix()}")
    sc.metadata.create_all(engine)
    return engine, generate_demo(engine, **kw)


def q(engine, sql):
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql))]


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    return make(tmp_path_factory.mktemp("demo"))


def test_counts_naming_and_roles(demo):
    engine, counts = demo
    assert counts["deliverables"] >= 120 and counts["runs"] > 500 and counts["dw_rows"] > 0
    names = q(engine, "SELECT name, is_demo FROM dossiers")
    assert len(names) == counts["dossiers"]
    assert all(n["name"].startswith("[DÉMO] ") and n["is_demo"] for n in names)
    assert {r["role"] for r in q(engine, "SELECT role FROM users")} == {"consultant", "reviewer"}


def test_is_demo_everywhere_in_dw(demo):
    engine, _ = demo
    checked = 0
    for table in dws.dw_metadata.tables.values():
        if "is_demo" in table.c:
            row = q(engine, f"SELECT COUNT(*) AS n, SUM(CASE WHEN is_demo THEN 1 ELSE 0 END) AS d "
                            f"FROM {table.name}")[0]
            assert row["n"] > 0 and row["n"] == row["d"], table.name
            checked += 1
    assert checked >= 13


def test_only_formats_the_ingestion_accepts(demo):
    used = {r["mime"] for r in q(demo[0], "SELECT DISTINCT mime FROM documents")}
    assert used and used <= set(MIME.values())


def test_every_transition_is_allowed_by_the_product(demo):
    engine, _ = demo
    moves = q(engine, "SELECT from_state, to_state, user_id, reason, deliverable_id "
                      "FROM state_transitions")
    authors = {d["id"]: d["author_id"] for d in q(engine, "SELECT id, author_id FROM deliverables")}
    states = set(getattr(State, "__args__", ()))
    for m in moves:
        assert (m["from_state"], m["to_state"]) in ALLOWED
        assert not states or m["to_state"] in states
        if m["to_state"] in ("approved", "rejected"):
            assert m["user_id"] != authors[m["deliverable_id"]]         # deux personnes (H6)
        if m["to_state"] == "rejected":
            assert m["reason"]                                          # motif obligatoire


def test_there_is_work_to_steer(demo):
    engine, _ = demo
    states = {r["state"]: r["n"] for r in q(
        engine, "SELECT state, COUNT(*) AS n FROM v_deliverable GROUP BY state")}
    assert states["in_review"] >= 5 and states["draft"] >= 1 and states["rejected"] >= 2
    returned = q(engine, "SELECT reason_code FROM v_deliverable WHERE returned")
    assert returned and all(r["reason_code"] for r in returned)
    assert q(engine, "SELECT COUNT(*) AS n FROM v_action")[0]["n"] > 0
    overall = q(engine, "SELECT status FROM v_forecast WHERE client_key IS NULL "
                        "AND type_key IS NULL AND author_key IS NULL AND reviewer_key IS NULL")
    assert [r["status"] for r in overall] == ["ok"]


def test_configurations_follow_the_protocol(demo):
    """08 §6 : A sans recherche, C = B + LoRA, D = autre taille sans LoRA ; banc hors production."""
    engine, _ = demo
    by = {r["config_label"]: r for r in q(engine, "SELECT * FROM v_bench")}
    assert set(by) == set(BENCH) == {"A", "B", "C", "D"}
    a, b, c, d = (by[k] for k in "ABCD")
    assert not a["has_retrieval"] and b["has_retrieval"] and a["model_name"] == b["model_name"]
    assert c["model_name"] == b["model_name"] and c["adapter"] and not b["adapter"]
    assert d["model_name"] != b["model_name"] and not d["adapter"]
    assert all(r["simulated"] for r in by.values())
    assert b["decision"] == "reference" and a["decision"] == "worse"
    assert c["decision"] == "inconclusive" and c["delta_low"] <= 0 < c["delta_high"]
    assert {r["config_label"] for r in q(engine, "SELECT config_label FROM v_generation")} == {None}


def test_same_seed_same_rows_other_seed_differs(tmp_path):
    def snapshot(engine):
        out = q(engine, "SELECT * FROM v_outcome")
        return (q(engine, "SELECT * FROM v_deliverable ORDER BY deliverable_id"),
                kpi.tpv(q(engine, "SELECT * FROM v_generation")), kpi.minutes_saved(out))

    a, _ = make(tmp_path, "a.db", seed=7, weeks=4)
    b, _ = make(tmp_path, "b.db", seed=7, weeks=4)
    c, _ = make(tmp_path, "c.db", seed=8, weeks=4)
    assert snapshot(a) == snapshot(b) != snapshot(c)


def test_distributions_plausible(demo):
    engine, _ = demo
    out = q(engine, "SELECT * FROM v_outcome")
    assert 0.1 < kpi.mean_edit_ratio(out) < 0.4 and 0.1 < kpi.unchanged_rate(out) < 0.6
    assert kpi.tpv(q(engine, "SELECT * FROM v_generation")) == pytest.approx(0.82, abs=0.06)
    funnel = q(engine, "SELECT * FROM v_review_funnel")
    assert any(f["rejections"] for f in funnel) and any(f["approved_date_key"] for f in funnel)
    assert q(engine, "SELECT COUNT(*) AS n FROM v_security WHERE injection_alert_count > 0")[0]["n"] > 0


def test_forecast_scopes_support_row_level_security(demo):
    """Un périmètre par consultant et un par responsable, pour qu'aucun ne lise le total du cabinet."""
    engine, _ = demo
    roles = {r["user_key"]: r["role"] for r in q(engine, "SELECT user_key, role FROM v_person")}
    scopes = q(engine, "SELECT author_key, reviewer_key FROM v_forecast")
    assert {roles[s["author_key"]] for s in scopes if s["author_key"]} == {"consultant"}
    assert {roles[s["reviewer_key"]] for s in scopes if s["reviewer_key"]} == {"reviewer"}
    assert not any(s["author_key"] and s["reviewer_key"] for s in scopes)
    assert all(r["user_id"] for r in q(engine, "SELECT user_id FROM v_person"))
    assert q(engine, "SELECT COUNT(*) AS n FROM v_forecast_point")[0]["n"] > 0


def test_second_call_is_noop(demo):
    engine, counts = demo
    again = generate_demo(engine)
    assert again["dossiers"] == 0 and sum(again.values()) == 0
    assert q(engine, "SELECT COUNT(*) AS n FROM dossiers")[0]["n"] == counts["dossiers"]
