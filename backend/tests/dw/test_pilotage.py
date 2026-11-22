"""Règles de pilotage (docs/14) : recommandations, prédiction, risque, décision du banc."""

from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest
from sqlalchemy import text

from app.dw import pilotage, report
from app.dw.bench import bench_rows
from app.dw.etl import run_etl
from app.dw.views_sql import create_views
from eval.harness.bootstrap import bootstrap_ci
from eval.harness.report import decide_c_vs_b

from . import T0, build_operational


def deliverable(**kw):
    return {"deliverable_id": "d", "state": "draft", "state_age_hours": 1.0, "idle_hours": 1.0,
            "blocking_open": 0, "citations_invalid": 0, "refused_sections": 0, "returned": False, **kw}


@pytest.mark.parametrize(("case", "code"), [
    ({"state": "approved", "citations_invalid": 1}, "citation_restante"),
    ({"state": "in_review", "state_age_hours": 48.1}, "relecture_en_retard"),
    ({"state": "rejected", "returned": True}, "renvoi_a_reprendre"),
    ({"state": "in_review", "blocking_open": 1}, "bloquant_en_relecture"),
    ({"blocking_open": 2}, "bloquant_avant_soumission"),
    ({"refused_sections": 1}, "preuve_manquante"),
    ({"idle_hours": 120.1}, "brouillon_en_sommeil"),
])
def test_each_rule_fires_alone(case, code):
    assert pilotage.actions_for(deliverable(**case)) == [code]


def test_thresholds_are_strict_and_null_never_fires():
    assert pilotage.actions_for(deliverable(state="in_review", state_age_hours=48.0)) == []
    assert pilotage.actions_for(deliverable(idle_hours=120.0)) == []
    assert pilotage.actions_for(deliverable(state="approved", citations_invalid=None)) == []


def test_recommendations_follow_scope_priority_and_actor():
    ds = [deliverable(deliverable_id="a", state="in_review"),
          deliverable(deliverable_id="b", state="in_review"), deliverable(deliverable_id="c")]
    acts = [{"deliverable_id": "a", "rule_code": "relecture_en_retard"},
            {"deliverable_id": "c", "rule_code": "preuve_manquante"},
            {"deliverable_id": "hors_filtre", "rule_code": "citation_restante"}]
    got = pilotage.recommendations(ds, acts)
    assert [r["code"] for r in got] == ["relecture_en_retard", "preuve_manquante"]
    assert got[0]["finding"] == "Relectures en retard : 1 sur 2 (livrables en relecture)"
    assert [r["code"] for r in pilotage.recommendations(ds, acts, pilotage.CONSULTANT)] == [
        "preuve_manquante"]
    assert len(pilotage.recommendations(ds, acts, limit=1)) == 1


def test_reason_is_reduced_to_a_category():
    assert pilotage.reason_code("Le montant de 4 M€ est faux") == "chiffres"
    assert pilotage.reason_code("Preuve absente") == "sources"
    assert pilotage.reason_code("À revoir avec Dupont") == "autre"
    assert pilotage.reason_code(" ") is None


def test_weekly_counts_have_no_partial_week():
    end = datetime(2026, 11, 20, 18, tzinfo=UTC)
    start = end - timedelta(days=17)
    times = [end, end - timedelta(days=6), end - timedelta(days=8), end - timedelta(days=16)]
    assert pilotage.weekly_counts(times, start, end) == [1, 2]


def test_forecast_needs_history_and_volume():
    assert pilotage.forecast_load([9] * 18)["status"] == "insufficient"          # 9 origines
    assert pilotage.forecast_load([0] * 38 + [5])["status"] == "insufficient"    # 5 événements


def test_forecast_is_published_only_if_it_beats_the_naive_reference():
    noisy = [2, 8] * 4 + [8, 2] * 3 + [1, 9, 9, 1] * 6
    good = pilotage.forecast_load(noisy)
    assert good["status"] == "ok" and good["mae"] < good["mae_naive"]
    assert good["low"] <= good["point"] <= good["high"]
    trend = pilotage.forecast_load(list(range(1, 41)))                           # la naïve suit mieux
    assert trend["status"] == "not_better" and trend["point"] is None
    flat = pilotage.forecast_load([5] * 40)
    assert flat["status"] == "not_better"                                        # égalité : pas publiée


def test_forecast_series_is_regular_and_ends_on_the_prediction():
    end = datetime(2026, 11, 20, 18, tzinfo=UTC)
    counts = [2, 8] * 4 + [8, 2] * 3 + [1, 9, 9, 1] * 6 + [4]          # 39 semaines
    forecast = pilotage.forecast_load(counts)
    series = pilotage.forecast_series(counts, end, forecast)
    actual = [r for r in series if r["actual"] is not None]
    assert len(actual) == 19 and sum(r["actual"] for r in actual) == sum(counts[1:])
    days = [datetime.fromisoformat(r["period_end"]) for r in series]
    assert {b - a for a, b in pairwise(days)} == {timedelta(days=14)}
    last, anchor = series[-1], series[-2]
    assert last["actual"] is None and last["point"] == forecast["point"]
    assert last["low"] <= last["point"] <= last["high"]
    assert anchor["point"] == anchor["low"] == anchor["high"] == anchor["actual"]


def test_forecast_series_shows_no_future_without_a_published_forecast():
    end = datetime(2026, 11, 20, 18, tzinfo=UTC)
    series = pilotage.forecast_series([0] * 20, end, pilotage.forecast_load([0] * 20))
    assert len(series) == 10 and all(r["point"] is None for r in series)


def test_queue_priority_weighs_age_by_risk():
    assert pilotage.queue_priority(48, 0.5) == pytest.approx(3.0)
    assert pilotage.queue_priority(48, None) == pytest.approx(2.0)


def test_report_rounds_like_power_bi():
    assert (report.num(2.25, 1), report.num(10.5), report.num(7.675)) == ("2,3", "11", "8")
    assert report.pct(0.125) == "13 %"


def cases(rate_clean, rate_fragile, n=120):
    out = []
    for i in range(n):
        fragile = i % 2 == 1
        rate = rate_fragile if fragile else rate_clean
        at = T0 + timedelta(days=i)
        out.append({"submitted": at, "decided": at + timedelta(hours=5), "blocking": fragile,
                    "rejected": (i // 2) % 10 < rate * 10})
    return out


def test_risk_model_is_checked_against_the_global_rate():
    good = pilotage.risk_model(cases(0.1, 0.8))
    assert good["status"] == "ok" and good["brier"] < good["brier_naive"]
    assert good["groups"][True]["rate"] == pytest.approx(0.8) and good["groups"][True]["n"] == 60
    assert pilotage.risk_model(cases(0.3, 0.3))["status"] == "not_better"
    assert pilotage.risk_model(cases(0.1, 0.8, 30))["status"] == "insufficient"


def test_bench_rows_keep_the_reference_and_the_decision():
    def result(label, value):
        return {"config": label, "tpv_sections": [value] * 12, "versions": {"model": "m"},
                "params": {"retrieval": {"enabled": True}}, "metrics": {}}

    rows = bench_rows([result("B", 0.5), result("C", 0.4)], is_demo=False)
    assert [(r["config_label"], r["decision"]) for r in rows] == [("B", "reference"), ("C", "worse")]


def test_bench_decision_is_the_one_of_the_eval_harness():
    b = {"tpv_sections": [0.8, 0.7, 0.9, 0.75] * 8, "metrics": {"citation_validity": {"mean": 0.97}}}
    better = [min(1.0, v + d) for v, d in zip(b["tpv_sections"], [0.05, 0.02, 0.04, 0.03] * 8, strict=True)]
    same = [v + d for v, d in zip(b["tpv_sections"], [0.02, -0.02] * 16, strict=True)]
    for values, validity, expected in ((better, 0.97, "retain"), (better, 0.90, "unsafe"),
                                       (same, 0.97, "inconclusive")):
        c = {"tpv_sections": values, "metrics": {"citation_validity": {"mean": validity}}}
        mine, theirs = pilotage.bench_decision(c, b), decide_c_vs_b(c, b)
        assert mine["decision"] == expected
        assert (mine["decision"] == "retain") is theirs["retain_c"]
        assert (mine["low"], mine["high"]) == (theirs["ci_low"], theirs["ci_high"])
    assert pilotage.bootstrap_ci(b["tpv_sections"]) == bootstrap_ci(b["tpv_sections"])


def test_snapshot_measures_what_remains_after_approval(repo):
    info = build_operational(repo)
    run_etl(repo.engine, repo.engine, now=T0 + timedelta(days=10))
    create_views(repo.engine)
    with repo.engine.connect() as c:
        rows = {r.deliverable_id: r._mapping for r in c.execute(text("SELECT * FROM v_deliverable"))}
        fired = {(r.deliverable_id, r.rule_code) for r in c.execute(text("SELECT * FROM v_action"))}
        status = c.execute(text("SELECT DISTINCT status FROM v_forecast")).scalars().all()
    a, b = rows[info["dlv_a"]], rows[info["dlv_b"]]
    assert a["state"] == "approved" and (a["citations_total"], a["citations_invalid"]) == (3, 1)
    assert (info["dlv_a"], "citation_restante") in fired
    assert b["state"] == "in_review" and b["state_age_hours"] > pilotage.REVIEW_OVERDUE_HOURS
    assert (info["dlv_b"], "relecture_en_retard") in fired
    assert status == ["insufficient"]


def test_production_label_fits_the_warehouse(repo):
    """`services/generation.py` écrit « default » ; `dim_model.config_label` fait un caractère."""
    info = build_operational(repo)
    repo.record_run({"id": "run_prod", "dossier_id": info["a"], "kind": "findings", "provider": "o",
                     "model": "m", "config_label": "default", "status": "ok", "started_at": T0})
    run_etl(repo.engine, repo.engine)
    with repo.engine.connect() as c:
        labels = set(c.execute(text("SELECT config_label FROM dim_model")).scalars())
    assert "default" not in labels and None in labels
