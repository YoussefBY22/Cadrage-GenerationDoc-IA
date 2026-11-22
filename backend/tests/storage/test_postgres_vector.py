"""pgvector réel (lot T1) : le classement `<=>` doit égaler la force brute. Sauté sans TEST_POSTGRES_URL."""

import os

import pytest
from sqlalchemy import create_engine, text

from app.dw.demo import generate_demo
from app.storage.vector_search import BruteForceVectorSearch, PgVectorSearch

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def eng():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL absent")
    e = create_engine(url)
    generate_demo(e, seed=42)
    yield e
    e.dispose()


def test_pgvector_matches_bruteforce(eng):
    with eng.connect() as c:
        row = c.execute(text(
            "SELECT dossier_id, embedding::text FROM chunks WHERE embedding IS NOT NULL LIMIT 1")).first()
        assert row, "aucun passage avec embedding (jeu de démo attendu)"
        dossier, emb = row
        docs = [r[0] for r in c.execute(text(
            "SELECT DISTINCT document_id FROM chunks WHERE dossier_id = :d"), {"d": dossier})]
    query = [float(x) for x in emb.strip("[]").split(",")]
    pg = PgVectorSearch(eng).search(dossier, query, 5)
    bf = BruteForceVectorSearch(eng).search(dossier, query, 5)
    assert pg and [i for i, _ in pg] == [i for i, _ in bf]
    assert pg[0][1] == pytest.approx(1.0, abs=1e-6)
    filtered = PgVectorSearch(eng).search(dossier, query, 5, document_ids=docs[:1])
    assert filtered and all(i in {j for j, _ in PgVectorSearch(eng).search(dossier, query, 500, docs[:1])}
                            for i, _ in filtered)
