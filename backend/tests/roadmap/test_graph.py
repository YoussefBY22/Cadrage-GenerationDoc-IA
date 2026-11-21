import pytest

from app.domain.roadmap import Initiative
from app.roadmap.graph import analyze


def n(id_, deps=(), dur=None):
    return Initiative(id=id_, title=id_, description="", finding_ids=[], scores=[],
                      depends_on=list(deps), duration_weeks=dur)


def test_vide():
    assert analyze([]) == ([], [], [])


def test_cycle_detecte():
    order, cycles, cp = analyze([n("A", ["C"]), n("B", ["A"]), n("C", ["B"])])
    assert cycles == [["A", "B", "C"]] and cp == [] and order == []


def test_cycles_multiples():
    _, cycles, _ = analyze([n("A", ["B", "C"]), n("B", ["A"]), n("C", ["A"])])
    assert cycles == [["A", "B"], ["A", "C"]]


def test_diamant_chemin_critique():
    ini = [n("A", dur=2), n("B", ["A"], dur=5), n("C", ["A"], dur=1), n("D", ["B", "C"], dur=3)]
    order, cycles, cp = analyze(ini)
    assert order == ["A", "B", "C", "D"] and cycles == [] and cp == ["A", "B", "D"]


def test_duree_absente_vaut_un_et_egalite():
    _, _, cp = analyze([n("A"), n("B", ["A"]), n("C", ["A"])])
    assert cp == ["A", "B"]


def test_ordre_stable_par_id():
    order, _, _ = analyze([n("c"), n("b"), n("a", ["c"])])
    assert order == ["b", "c", "a"]


def test_dependance_inconnue():
    with pytest.raises(ValueError, match="inconnu"):
        analyze([n("A", ["X"])])
