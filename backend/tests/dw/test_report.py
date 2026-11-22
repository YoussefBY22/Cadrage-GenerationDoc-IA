"""Rapport de pilotage : mêmes règles que le tableau de bord, et jamais destiné au client."""

import pytest
from docx import Document
from sqlalchemy import create_engine

from app.dw import pilotage, report
from app.dw.demo import generate_demo
from app.storage import schema as sc


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    e = create_engine(f"sqlite+pysqlite:///{(tmp_path_factory.mktemp('r') / 'r.db').as_posix()}")
    sc.metadata.create_all(e)
    generate_demo(e)
    return e


def text_of(path) -> str:
    doc = Document(str(path))
    cells = [c.text for t in doc.tables for row in t.rows for c in row.cells]
    return "\n".join([p.text for p in doc.paragraphs] + cells)


def test_internal_report_has_every_part(engine, tmp_path):
    body = text_of(report.write_report(engine, report.Scope(), tmp_path / "r.docx"))
    for part in ("Synthèse", "Recommandations prioritaires", "Critères de réussite", "Indicateurs",
                 "Charge de relecture", "Limites", "Situation au 20/11/2026", report.SIMULATION):
        assert part in body
    assert "Non mesuré" in body and "Temps gagné" not in body


def test_filters_reach_kpis_and_recommendations(engine):
    everyone = report.collect(engine, report.Scope())
    one = report.collect(engine, report.Scope(consultant="[DÉMO] Consultant 2"))
    assert 0 < one["approved"] < everyone["approved"]
    assert one["to_review"] <= everyone["to_review"]
    assert len(everyone["recommendations"]) == pilotage.MAX_RECOMMENDATIONS
    assert one["forecast"]["author_key"] is not None and everyone["forecast"]["author_key"] is None


def test_filtered_report_stays_internal(engine, tmp_path):
    body = text_of(report.write_report(engine, report.Scope(client="Société Démo 2"), tmp_path / "c.docx"))
    assert "Société Démo 2" in body and report.INTERNAL_NOTICE in body
    assert "Société Démo 1" not in body and "Société Démo 3" not in body


def test_there_is_no_client_audience(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["report", "--audience", "client", "--client", "X"])
    with pytest.raises(SystemExit):
        report.main()
    assert "unrecognized arguments: --audience" in capsys.readouterr().err


def test_no_rate_and_no_verdict_without_measure(engine):
    assert "insuffisant" in report.rate(3, pilotage.MIN_SAMPLE - 1)
    assert "%" in report.rate(3, pilotage.MIN_SAMPLE)
    empty = report.collect(engine, report.Scope()) | {"simulated": False, "invalid_left": None, "written": 4, "unchanged": 4}
    verdicts = [row[3] for row in report.h7_rows(empty)]
    assert verdicts == ["Non mesuré", "Effectif insuffisant"]


@pytest.mark.parametrize(("measured", "left", "verdict"), [
    (1, 0, "Effectif insuffisant"),          # zéro sur un livrable ne prouve rien
    (1, 2, "Non atteint"),                   # une citation restante suffit à échouer
    (pilotage.MIN_SAMPLE, 0, "Atteint"),
])
def test_h7_citations_needs_a_sample_to_pass(engine, measured, left, verdict):
    data = report.collect(engine, report.Scope()) | {
        "simulated": False, "approved": measured, "measured": measured, "invalid_left": left}
    assert report.h7_rows(data)[0][3] == verdict


def test_invented_data_measures_no_model_quality(engine):
    data = report.collect(engine, report.Scope())
    assert data["simulated"]
    assert {row[3] for row in report.h7_rows(data)} == {"Non mesuré"}
    assert all(d["risk"] is None for d in data["queue"])
    assert "Fiabilité non mesurée." in report.forecast_lines(data)


def test_internal_report_keeps_proofs_out_of_the_page(engine, tmp_path):
    body = text_of(report.write_report(engine, report.Scope(), tmp_path / "s.docx"))
    for word in ("Décision liée", "Seuil", "Brier", "TPV", "naïve", "H7"):
        assert word not in body
