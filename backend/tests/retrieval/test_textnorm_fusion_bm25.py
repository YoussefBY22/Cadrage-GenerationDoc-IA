import math

import pytest

from app.retrieval.bm25 import BM25Index
from app.retrieval.fusion import rrf
from app.retrieval.textnorm import tokenize


def test_tokenize_accents_et_mots_vides():
    assert tokenize("Les ÉQUIPES de la Gouvernance") == tokenize("equipes gouvernance")
    assert "le" not in tokenize("le the and de")
    assert tokenize("le the and de") == []


def test_tokenize_nombres_conserves():
    assert "1250" in tokenize("Budget de 1 250 euros")
    assert "1250" in tokenize("Budget de 1 250 euros")
    assert "15%" in tokenize("une hausse de 15 % par an")
    assert "15%" in tokenize("15% de hausse")
    assert "1250000" in tokenize("1 250 000")
    assert "3,5" in tokenize("taux de 3,5")


def test_tokenize_racinisation():
    assert tokenize("gouvernances") == tokenize("gouvernance")
    assert tokenize("running", "en") == tokenize("runs", "en")


def test_rrf_valeurs_exactes():
    res = dict(rrf([["a", "b"], ["b", "c"]]))
    assert res["a"] == pytest.approx(1 / 61)
    assert res["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert res["c"] == pytest.approx(1 / 62)
    assert [d for d, _ in rrf([["a", "b"], ["b", "c"]])] == ["b", "a", "c"]


def test_rrf_k_personnalise_et_vide():
    assert rrf([]) == []
    assert rrf([["x"]], k=10) == [("x", pytest.approx(1 / 11))]


def test_bm25_calcul_a_la_main():
    idx = BM25Index(k1=1.2, b=0.75)
    idx.add("d1", ["chat", "chat", "chien"])
    idx.add("d2", ["chien", "oiseau"])
    idx.add("d3", ["oiseau", "poisson", "poisson", "poisson"])
    avgdl = (3 + 2 + 4) / 3

    def score(tf, dl, n):
        idf = math.log(1 + (3 - n + 0.5) / (n + 0.5))
        return idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * dl / avgdl))

    res = dict(idx.search(["chat"], 10))
    assert list(res) == ["d1"]
    assert res["d1"] == pytest.approx(score(2, 3, 1))

    res = idx.search(["chien"], 10)
    assert [c for c, _ in res] == ["d2", "d1"]  # d2 plus court
    assert res[0][1] == pytest.approx(score(1, 2, 2))
    assert res[1][1] == pytest.approx(score(1, 3, 2))

    res = dict(idx.search(["chat", "poisson"], 10))
    assert res["d1"] == pytest.approx(score(2, 3, 1))
    assert res["d3"] == pytest.approx(score(3, 4, 1))
    assert idx.search(["inconnu"], 5) == []
    assert len(idx.search(["chien", "oiseau"], 1)) == 1
