"""Objectif, résultat et indicateur sont des propositions IA : les nombres absents des sources sont signalés."""

from __future__ import annotations

import re
import unicodedata

_WORDS = ["deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize", "vingt", "trente", "quarante", "cinquante", "soixante", "cent", "mille", "million", "milliard"]
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _plain(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def numbers_in(text: str) -> list[str]:
    """Nombres écrits en chiffres ou en lettres (« 15 », « trois »), sans doublon, dans l'ordre."""
    found = [m.group(0).replace(",", ".") for m in _NUM.finditer(text)]
    words = set(re.findall(r"[a-z]+", _plain(text)))
    found += [w for w in _WORDS if w in words]
    return list(dict.fromkeys(found))


def unsourced_numbers(proposal: str, sources: list[str]) -> list[str]:
    """Nombres de la proposition qui n'apparaissent dans aucun texte source."""
    have = {n for s in sources for n in numbers_in(s)}
    return [n for n in numbers_in(proposal) if n not in have]
