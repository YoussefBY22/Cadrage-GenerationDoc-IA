"""Nombres en lettres et fourchettes perdues."""

from decimal import Decimal

import pytest

from app.domain.documents import Chunk
from app.domain.generation import SectionDraft, Sentence
from app.verification import verify_section
from app.verification.numbers import extract_numbers


@pytest.mark.parametrize(
    ("text", "lang", "expected"),
    [
        ("vingt-cinq agents", "fr", [25]),
        ("soixante-dix-sept sites", "fr", [77]),
        ("quatre-vingts écoles", "fr", [80]),
        ("quatre-vingt-dix-neuf cas", "fr", [99]),
        ("vingt et un jours", "fr", [21]),
        ("trois cent douze postes", "fr", [312]),
        ("deux mille vingt-six", "fr", [2026]),
        ("dix-huit mois", "fr", [18]),
        ("un million de francs", "fr", [1000000]),
        ("deux et trois", "fr", [2, 3]),
        ("une stratégie et un outil neuf", "fr", []),
        ("des millions de personnes", "fr", []),
        ("20 pour cent des agents", "fr", [20]),
        ("twenty-five staff", "en", [25]),
        ("one hundred and five sites", "en", [105]),
        ("one of the plans", "en", []),
    ],
)
def test_words(text, lang, expected):
    assert [n.value for n in extract_numbers(text, lang)] == [Decimal(x) for x in expected]


def test_percent_in_words():
    (n,) = extract_numbers("vingt pour cent des agents")
    assert (n.value, n.is_percent) == (Decimal(20), True)


def _issues(sentence, source, kind="fact"):
    chunk = Chunk(id="c1", document_id="doc", dossier_id="d", ordinal=0, text=source,
                  page_start=1, page_end=1, section_path=(), token_estimate=20)
    s = Sentence(text=sentence, kind=kind, source_ids=["c1"])
    draft = SectionDraft(section_key="s", status="ok", sentences=[s])
    report = verify_section(draft, {"c1": chunk}, dossier_id="d", support_threshold=0)
    return {(i.code, i.severity) for i in report.issues}


@pytest.mark.parametrize(
    ("sentence", "source", "expected"),
    [
        ("Le service compte vingt-cinq agents.", "Le service compte 32 agents.", {("NUMBER_NOT_FOUND", "blocking")}),
        ("Le service compte vingt-cinq agents.", "Le service compte 25 agents.", set()),
        ("Le service compte 25 agents.", "Le service compte vingt-cinq agents.", set()),
        ("Les deux volets sont liés.", "Le volet A et le volet B sont liés.", {("NUMBER_NOT_FOUND", "warning")}),
        ("La baisse est de 20 %.", "La baisse est de 10 à 20 %.", {("RANGE_LOST", "warning")}),
        ("La baisse est de 10 à 20 %.", "La baisse est de 10 à 20 %.", set()),
        ("Il faut cinq mois.", "Il faut entre trois et cinq mois.", {("RANGE_LOST", "warning")}),
        ("La baisse est de 20 %.", "Baisse de 10 à 20 %, confirmée à 20 %.", set()),
    ],
)
def test_verifier(sentence, source, expected):
    assert _issues(sentence, source) == expected


def test_transition():
    assert _issues("Voici les deux volets.", "x", "transition") == set()
    assert _issues("Voici les trois cents sites.", "x", "transition") == {("TRANSITION_WITH_NUMBER", "blocking")}
