"""Lot REF : normalisation des étiquettes COBIT 2019 / ITIL 4 d'une initiative."""

import pytest

from app.domain.roadmap import Initiative
from app.roadmap.referentiels import COBIT_OBJECTIVES, ITIL_PRACTICES, normalize_domain


def test_comptes():
    assert len(COBIT_OBJECTIVES) == 40 and len(ITIL_PRACTICES) == 34


@pytest.mark.parametrize("raw,expected", [
    ("APO12", "COBIT APO12"), ("COBIT apo-12", "COBIT APO12"), ("bai1", "COBIT BAI01"),
    ("ITIL incident management", "ITIL Incident management"),
    ("ITIL 4: Risk management", "ITIL Risk management"),
    ("APO15", None), ("XYZ01", None), ("ITIL magie", None), ("", None), (None, None),
])
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


def test_initiative_domaine_facultatif_et_compatible():
    ini = Initiative(id="i", title="t", description="d", finding_ids=["f"], scores=[])
    assert ini.domain is None
    assert Initiative.model_validate(ini.model_dump(exclude={"domain"})).domain is None
