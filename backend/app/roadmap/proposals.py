"""Objectif, résultat et indicateur sont des propositions IA : les nombres absents des sources sont signalés."""

from __future__ import annotations

import re
import unicodedata

_VALUES = {w: n for n, w in enumerate(
    ["deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize"], 2)}
_VALUES.update({"dix-sept": 17, "dix-huit": 18, "dix-neuf": 19, "vingt": 20, "trente": 30,
                "quarante": 40, "cinquante": 50, "soixante": 60, "cent": 100, "mille": 1000,
                "million": 10**6, "milliard": 10**9})
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _plain(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _tokens(text: str) -> list[tuple[float, str]]:
    """(valeur, forme écrite) : « 2 » et « deux » ont la même valeur."""
    out = [(float(m.group(0).replace(",", ".")), m.group(0).replace(",", "."))
           for m in _NUM.finditer(text)]
    words = set(re.findall(r"[a-z]+(?:-[a-z]+)?", _plain(text)))
    out += [(float(_VALUES[w]), w) for w in _VALUES if w in words]
    return out


def numbers_in(text: str) -> list[str]:
    """Nombres écrits en chiffres ou en lettres (« 15 », « trois »), sans doublon, dans l'ordre."""
    return list(dict.fromkeys(raw for _, raw in _tokens(text)))


def unsourced_numbers(proposal: str, sources: list[str]) -> list[str]:
    """Nombres de la proposition dont la VALEUR n'apparaît dans aucune source (« deux » = « 2 »)."""
    have = {v for s in sources for v, _ in _tokens(s)}
    return list(dict.fromkeys(raw for v, raw in _tokens(proposal) if v not in have))
