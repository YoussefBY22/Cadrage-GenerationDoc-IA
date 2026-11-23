"""Export CSV : un fichier par vue, BOM UTF-8, séparateurs selon la locale, contenu = vues."""

import csv

import pytest
from sqlalchemy import text

from app.dw.etl import run_etl
from app.dw.export_csv import export_csv
from app.dw.views_sql import VIEWS

from . import build_operational


@pytest.fixture
def loaded(repo):
    build_operational(repo)
    run_etl(repo.engine, repo.engine)
    return repo.engine


def read(path, delimiter):
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "BOM UTF-8 attendu"
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f, delimiter=delimiter))


def view_rows(engine, name):
    with engine.connect() as c:
        res = c.execute(text(f"SELECT * FROM {name}"))
        return list(res.keys()), [tuple(r) for r in res]


def test_one_csv_per_view_matches_views(loaded, tmp_path):
    counts = export_csv(loaded, tmp_path)
    assert set(counts) == set(VIEWS)
    for name in VIEWS:
        cols, rows = view_rows(loaded, name)
        table = read(tmp_path / f"{name}.csv", ";")
        assert table[0] == cols and len(table) - 1 == len(rows) == counts[name]


def test_french_locale_uses_decimal_comma(loaded, tmp_path):
    export_csv(loaded, tmp_path, "fr")
    table = read(tmp_path / "v_generation.csv", ";")
    header = table[0]
    run1 = next(r for r in table[1:] if r[header.index("run_id")] == "run_1")
    assert run1[header.index("tpv")] == "0,5" and run1[header.index("client_name")] == "Acme SA"


def test_english_locale(loaded, tmp_path):
    export_csv(loaded, tmp_path, "en")
    table = read(tmp_path / "v_generation.csv", ",")
    header = table[0]
    run1 = next(r for r in table[1:] if r[header.index("run_id")] == "run_1")
    assert run1[header.index("tpv")] == "0.5"


def test_null_and_bool_cells_and_bad_locale(loaded, tmp_path):
    export_csv(loaded, tmp_path)
    table = read(tmp_path / "v_generation.csv", ";")
    header = table[0]
    run3 = next(r for r in table[1:] if r[header.index("run_id")] == "run_3")
    assert run3[header.index("tpv")] == ""                 # NULL → cellule vide
    with pytest.raises(ValueError):
        export_csv(loaded, tmp_path, "de")


def test_demo_roundtrip(tmp_path):
    from sqlalchemy import create_engine

    from app.dw.demo import generate_demo
    from app.storage import schema as sc

    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'x.db').as_posix()}")
    sc.metadata.create_all(engine)
    generate_demo(engine, weeks=3)
    counts = export_csv(engine, tmp_path / "out")
    cols, rows = view_rows(engine, "v_quality_by_model")
    table = read(tmp_path / "out" / "v_quality_by_model.csv", ";")
    assert len(table) - 1 == len(rows) == counts["v_quality_by_model"] and table[0] == cols
    tpv_col = cols.index("tpv")
    got = sorted(float(r[tpv_col].replace(",", ".")) for r in table[1:] if r[tpv_col])
    assert got == pytest.approx(sorted(r[tpv_col] for r in rows if r[tpv_col] is not None), abs=1e-9)
