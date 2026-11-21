"""Extraction des nombres : 40 cas FR/EN dont les pièges."""

from decimal import Decimal as D

import pytest

from app.verification.numbers import extract_numbers

P = True
CASES = [
    ("2.1 Contexte général", []),
    ("1. Introduction aux enjeux", []),
    ("2) Les risques", []),
    ("1.2.3 Périmètre", []),
    ("3.5 Millions de m3 perdus", [(D(3500000), False)]),
    ("1 250,5 mégawatts", [(D("1250.5"), False)]),
    ("1 250 agents", [(D(1250), False)]),
    ("1 250 agents", [(D(1250), False)]),
    ("3,2 Md€ de pertes", [(D(3200000000), False)]),
    ("15 pour cent des sites", [(D(15), P)]),
    ("15 % des sites", [(D(15), P)]),
    ("15% des sites", [(D(15), P)]),
    ("taux de 32,5 %", [(D("32.5"), P)]),
    ("rate of 12.5 percent", [(D("12.5"), P)]),
    ("1,5 million d'euros", [(D(1500000), False)]),
    ("2 millions de m3", [(D(2000000), False)]),
    ("4 milliards d'euros", [(D(4000000000), False)]),
    ("12 k€ par mois", [(D(12000), False)]),
    ("budget de 3 M€", [(D(3000000), False)]),
    ("5 mille tonnes", [(D(5000), False)]),
    ("1,250,000 users", [(D(1250000), False)]),
    ("1,250 users", [(D("1.25"), False)]),
    ("1.250.000 habitants", [(D(1250000), False)]),
    ("price of 3.2 billion", [(D("3.2"), False)]),
    ("en 2023 et 2024", [(D(2023), False), (D(2024), False)]),
    ("Le service compte 42 agents", [(D(42), False)]),
    ("Aucun chiffre ici", []),
    ("P2 et T3 sont des étiquettes", []),
    ("versus 0,5 point", [(D("0.5"), False)]),
    ("de 10 à 20 jours", [(D(10), False), (D(20), False)]),
    ("7 mois de retard", [(D(7), False)]),
    ("2 Mars", [(D(2), False)]),
    ("15 pour cent", [(D(15), P)]),
    ("   3. Les actions", []),
    ("- 4) Les actions", []),
    ("12 345 dossiers en retard", [(D(12345), False)]),
    ("12/05/2023", [(D(12), False), (D(5), False), (D(2023), False)]),
    ("100 % d'accès", [(D(100), P)]),
    ("0,75 pour cent", [(D("0.75"), P)]),
    ("COVID-19", [(D(19), False)]),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_extract_numbers(text, expected):
    got = [(n.value, n.is_percent) for n in extract_numbers(text)]
    assert got == expected, text


def test_en_decimal_comma_thousands():
    assert extract_numbers("1,250 users", "en")[0].value == D(1250)


def test_span_and_raw():
    n = extract_numbers("taux de 32 %")[0]
    assert n.raw == "32 %" and n.span == (8, 12)


def test_forty_cases():
    assert len(CASES) >= 40
