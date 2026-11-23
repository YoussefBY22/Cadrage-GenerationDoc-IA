"""ETL (07 §11 points 1, 2, 3, 5, 6) sur SQLite, jeu opérationnel construit via SqlRepository."""

from datetime import timedelta

import pytest
from sqlalchemy import func, inspect, select, text

from app.dw import schema as dw
from app.dw.etl import run_etl
from app.dw.schema import bind_dw

from . import T0, build_operational

FACTS = ["fact_section_generation", "fact_citation_check", "fact_llm_call", "fact_review",
         "fact_section_outcome"]


@pytest.fixture
def ops(repo):
    return build_operational(repo)


def counts(repo, tables=None):
    eng = bind_dw(repo.engine)
    out = {}
    with eng.connect() as c:
        for t in tables or dw.dw_metadata.tables.values():
            t = dw.dw_metadata.tables[f"dw.{t}"] if isinstance(t, str) else t
            out[t.name] = c.execute(select(func.count()).select_from(t)).scalar()
    return out


def test_etl_counts(repo, ops):
    res = run_etl(repo.engine, repo.engine, now=T0 + timedelta(hours=5))
    assert res["fact_section_generation"] == 5
    assert res["fact_review"] == 3
    assert res["fact_section_outcome"] == 2
    n = counts(repo)
    assert n["fact_section_generation"] == 5
    assert n["fact_citation_check"] == 5          # r1:3 + r2:1 + r4:1
    assert n["fact_llm_call"] == 6                # r2 a 2 tentatives
    assert n["fact_review"] == 3 and n["fact_section_outcome"] == 2
    assert n["dim_client"] == 2 and n["dim_mission"] == 2 and n["dim_document"] == 2
    assert n["dim_user"] == 2 and n["dim_model"] == 4
    assert n["dim_date"] == 1461 and n["dim_state"] == 4 and n["dim_issue"] == 10
    assert n["dim_deliverable_type"] == 4
    assert n["etl_log"] == 1
    eng = bind_dw(repo.engine)
    with eng.connect() as c:
        g = {r.run_id: r for r in c.execute(select(dw.fact_section_generation))}
        assert (g["run_1"].sentences_total, g["run_1"].sentences_verified,
                g["run_1"].sentences_warning, g["run_1"].passages_retrieved) == (2, 1, 1, 2)
        assert (g["run_1"].citations_total, g["run_1"].citations_valid) == (3, 2)
        assert (g["run_2"].numbers_cited, g["run_2"].numbers_found, g["run_2"].attempts) == (2, 1, 2)
        assert g["run_4"].is_demo and not g["run_1"].is_demo
        calls = c.execute(select(dw.fact_llm_call).where(
            dw.fact_llm_call.c.tokens_out == 150).order_by(dw.fact_llm_call.c.call_key)).all()
        assert [(x.latency_ms, x.success) for x in calls] == [(1501, False), (1500, True)]
        o = {r.section_key: r for r in c.execute(select(dw.fact_section_outcome))}
        ctx = next(r for r in o.values() if r.generated_words == 8)
        assert ctx.edit_ratio == pytest.approx(0.125) and not ctx.unchanged
        other = next(r for r in o.values() if r is not ctx)
        assert other.unchanged and other.edit_ratio == 0
        rev = {r.transition_id: r for r in c.execute(select(dw.fact_review))}
        approved = next(r for r in rev.values() if r.to_state_key == 3)
        assert float(approved.hours_since_submission) == 2.0   # 3 h - 1 h
        assert float(approved.hours_since_previous) == 2.0 and approved.has_reason
        wm = {r.source_table for r in c.execute(select(dw.etl_watermark))}
        assert wm == {"generation_runs", "state_transitions", "deliverable_versions"}


def test_idempotent(repo, ops):
    run_etl(repo.engine, repo.engine)
    before = counts(repo)
    again = run_etl(repo.engine, repo.engine)
    full = run_etl(repo.engine, repo.engine, full=True)
    assert all(v == 0 for k, v in again.items() if k in FACTS)
    assert all(v == 0 for k, v in full.items() if k in FACTS)
    after = counts(repo)
    after["etl_log"] = before["etl_log"]
    assert after == before


def test_incremental_one_new_run(repo, ops):
    run_etl(repo.engine, repo.engine)
    before = counts(repo)
    ops["run"](6, ops["a"], "section", "objectifs", ops["dlv_a"], "B", "ok", 600)
    res = run_etl(repo.engine, repo.engine)
    assert res["fact_section_generation"] == 1 and res["fact_llm_call"] == 1
    after = counts(repo, FACTS)
    assert after["fact_section_generation"] == before["fact_section_generation"] + 1
    assert after["fact_review"] == before["fact_review"]
    # un run plus ancien que le filigrane (hors fenêtre de 5 min) n'est lu qu'avec --full
    ops["run"](7, ops["a"], "section", "contexte", ops["dlv_a"], "B", "ok", 1)
    assert run_etl(repo.engine, repo.engine).get("fact_section_generation", 0) == 0
    assert run_etl(repo.engine, repo.engine, full=True)["fact_section_generation"] == 1


def test_pseudonymization(repo, ops):
    run_etl(repo.engine, repo.engine, pseudonymize=True)
    eng = bind_dw(repo.engine)
    with eng.connect() as c:
        names = [r[0] for r in c.execute(select(dw.dim_client.c.client_name))]
        assert sorted(names) == ["Client 001", "Client 002"]
        blob = " ".join(names + [r[0] for r in c.execute(select(dw.dim_mission.c.mission_name))]
                        + [r[0] for r in c.execute(select(dw.dim_user.c.user_label))])
    for secret in ("Acme", "Beta", "Camille", "Mission Acme"):
        assert secret not in blob
    # désactivée : noms réels
    run_etl(repo.engine, repo.engine, pseudonymize=False)
    with eng.connect() as c:
        assert {r[0] for r in c.execute(select(dw.dim_client.c.client_name))} == {"Acme SA",
                                                                                   "Beta Corp"}


def test_no_free_text_columns():
    """Liste blanche : aucune colonne texte de plus de 200 caractères dans dw."""
    from sqlalchemy import String, Text
    wide = [f"{t.name}.{c.name}" for t in dw.dw_metadata.tables.values() for c in t.columns
            if isinstance(c.type, Text) or (isinstance(c.type, String) and (c.type.length or 0) > 200)]
    assert wide == []


def test_etl_log_and_error(repo, ops):
    run_etl(repo.engine, repo.engine, now=T0)
    eng = bind_dw(repo.engine)
    with eng.connect() as c:
        row = c.execute(select(dw.etl_log)).one()
        assert row.status == "ok" and row.rows_by_table["fact_section_generation"] == 5
    # panne côté source : journal en erreur, exception propagée
    with repo.engine.begin() as c:
        c.execute(text("ALTER TABLE state_transitions RENAME TO st_old"))
    try:
        with pytest.raises(Exception):  # noqa: B017
            run_etl(repo.engine, repo.engine)
    finally:
        with repo.engine.begin() as c:
            c.execute(text("ALTER TABLE st_old RENAME TO state_transitions"))
    with eng.connect() as c:
        assert [r.status for r in c.execute(select(dw.etl_log).order_by(dw.etl_log.c.id))] == [
            "ok", "error"]


def test_tables_coexist_with_operational(repo, ops):
    run_etl(repo.engine, repo.engine)
    names = set(inspect(repo.engine).get_table_names())
    assert {"fact_review", "dim_client", "chunks"} <= names
