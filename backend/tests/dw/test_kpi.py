"""Indicateurs : fonctions pures testées sur des lignes calculées à la main (07 §5)."""

import pytest

from app.dw import kpi


def gen(status="ok", total=0, verified=0, cit_total=0, cit_valid=0, cited=0, found=0):
    return {"status": status, "sentences_total": total, "sentences_verified": verified,
            "citations_total": cit_total, "citations_valid": cit_valid,
            "numbers_cited": cited, "numbers_found": found}


GENS = [gen(total=4, verified=3, cit_total=5, cit_valid=4, cited=2, found=1),
        gen(total=6, verified=3, cit_total=5, cit_valid=1, cited=3, found=3),
        gen(status="refused"), gen(status="invalid"),
        gen(status="error", total=9, verified=9)]   # ignorée par TPV (statut ≠ ok)


def test_generation_kpis():
    assert kpi.tpv(GENS) == pytest.approx(6 / 10)
    assert kpi.citations_valid_rate(GENS) == pytest.approx(5 / 10)
    assert kpi.number_fidelity(GENS) == pytest.approx(4 / 5)
    assert kpi.refusal_rate(GENS) == pytest.approx(1 / 5)
    assert kpi.invalid_rate(GENS) == pytest.approx(1 / 5)


def test_empty_and_edge_cases():
    assert kpi.tpv([]) is None and kpi.refusal_rate([]) is None
    assert kpi.number_fidelity([gen()]) == 1.0            # aucun chiffre cité
    assert kpi.tpv([gen(status="refused")]) is None
    assert kpi.unchanged_rate([]) is None and kpi.mean_edit_ratio([]) is None
    assert kpi.percentile([], 0.5) is None and kpi.review_delay_hours([]) is None
    assert kpi.review_rejection_rate([]) is None and kpi.throughput_tokens_per_s([]) is None


OUT = [{"unchanged": True, "edit_ratio": 0.0, "minutes_saved_est": 30.0},
       {"unchanged": False, "edit_ratio": 0.25, "minutes_saved_est": 22.5},
       {"unchanged": False, "edit_ratio": 0.75, "minutes_saved_est": 7.5},
       {"unchanged": True, "edit_ratio": 0.0, "minutes_saved_est": 30.0}]


def test_outcome_kpis():
    assert kpi.unchanged_rate(OUT) == 0.5
    assert kpi.mean_edit_ratio(OUT) == pytest.approx(0.25)
    assert kpi.minutes_saved(OUT) == pytest.approx(90.0)


def test_percentile_matches_inclusive_definition():
    xs = [10, 20, 30, 40]
    assert kpi.percentile(xs, 0.5) == 25
    assert kpi.percentile(xs, 0.95) == pytest.approx(38.5)
    assert kpi.percentile(xs, 0) == 10 and kpi.percentile(xs, 1) == 40
    assert kpi.percentile([7], 0.95) == 7


def test_calls_and_throughput():
    calls = [{"latency_ms": 1000, "tokens_out": 100}, {"latency_ms": 3000, "tokens_out": 100},
             {"latency_ms": None, "tokens_out": 5}]
    assert kpi.latency_percentile(calls, 0.5) == 2000
    assert kpi.throughput_tokens_per_s(calls) == pytest.approx(200 / 4.0)


def test_review_kpis():
    rv = [{"to_state": "in_review", "hours_since_submission": 0},
          {"to_state": "rejected", "hours_since_submission": 4},
          {"to_state": "in_review", "hours_since_submission": 5},
          {"to_state": "approved", "hours_since_submission": 10},
          {"to_state": "in_review", "hours_since_submission": 0},
          {"to_state": "approved", "hours_since_submission": 2}]
    assert kpi.review_delay_hours(rv) == 6.0               # médiane de 10 et 2
    assert kpi.review_rejection_rate(rv) == pytest.approx(1 / 3)


def test_injection_alerts():
    assert kpi.injection_alerts([{"injection_alert_count": 2}, {"injection_alert_count": 3}]) == 5
