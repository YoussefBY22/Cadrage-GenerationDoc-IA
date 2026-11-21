import pytest

from app.domain.roadmap import Criterion, CriterionScore, Initiative
from app.roadmap.scoring import DEFAULT_CRITERIA, explain, score, score_with_warnings

KEYS = ["impact", "urgence", "faisabilite", "cout", "risque"]


def ini(id_, vals, deps=()):
    return Initiative(
        id=id_, title=id_, description="", finding_ids=[],
        scores=[CriterionScore(key=k, value=v, source_ids=[], rationale="") for k, v in zip(KEYS, vals)],
        depends_on=list(deps),
    )


def test_calcul_a_la_main_quatre_initiatives():
    # A : 5,5,5, coût 1, risque 1 -> 0.35+0.25+0.2+0.1+0.1 = 1.0 ; B : tout à 3 -> 0.5
    # C : 0.35*1 + 0 + 0.2*0.5 + 0.1*0.75 + 0.1*0.25 = 0.55 ; D : 1,1,1,5,5 -> 0
    items = score([ini("D", [1, 1, 1, 5, 5]), ini("B", [3] * 5),
                   ini("A", [5, 5, 5, 1, 1]), ini("C", [5, 1, 3, 2, 4])], DEFAULT_CRITERIA)
    assert [(i.initiative.id, i.score, i.rank) for i in items] == [
        ("A", 1.0, 1), ("C", 0.55, 2), ("B", 0.5, 3), ("D", 0.0, 4)]
    assert [i.wave for i in items] == [1, 2, 3, 3]


def test_inversion_cout():
    bas, haut = score([ini("X", [3, 3, 3, 1, 3]), ini("Y", [3, 3, 3, 5, 3])], DEFAULT_CRITERIA)
    assert bas.initiative.id == "X" and bas.score > haut.score


def test_egalite_par_id():
    items = score([ini("b", [3] * 5), ini("a", [3] * 5)], DEFAULT_CRITERIA)
    assert [i.initiative.id for i in items] == ["a", "b"]


def test_poids_non_normalises():
    crit = [Criterion(key="impact", label="I", weight=3), Criterion(key="urgence", label="U", weight=1)]
    (it,) = score([ini("A", [5, 1, 1, 1, 1])], crit)
    assert it.score == 0.75


def test_vagues_reportees_apres_prerequis():
    a = ini("a", [5, 5, 5, 1, 1], deps=["z"])
    z = ini("z", [1, 1, 1, 5, 5])
    items = {i.initiative.id: i for i in score([a, z], DEFAULT_CRITERIA, waves=2)}
    assert items["a"].rank == 1 and items["a"].wave == 2 and items["z"].wave == 2


def test_critere_manquant_avertissement():
    partiel = Initiative(id="p", title="p", description="", finding_ids=[], scores=[])
    items, warns = score_with_warnings([partiel], DEFAULT_CRITERIA)
    assert items[0].score == 0.2 and len(warns) == 5  # coût et risque inversés -> 0,2 au total


def test_explain():
    (it,) = score([ini("A", [5, 5, 5, 1, 1])], DEFAULT_CRITERIA)
    txt = explain(it)
    assert txt.startswith("score = 0,35×1,00") and "= 1,0000" in txt and "inversé" in txt


def test_poids_nul():
    with pytest.raises(ValueError):
        score([ini("A", [1] * 5)], [])
