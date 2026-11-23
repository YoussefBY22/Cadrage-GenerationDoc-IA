"""Nombres écrits en lettres (FR/EN)."""

import re
from collections.abc import Iterator

from app.domain.ids import Lang

_UNITS = {
    "fr": "zéro un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize",
    "en": (
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
        "sixteen seventeen eighteen nineteen"
    ),
}
_TENS = {
    "fr": {"vingt": 20, "vingts": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60},
    "en": {
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    },
}
_HUNDRED = {"fr": {"cent", "cents"}, "en": {"hundred"}}
_SCALE = {
    "fr": {"mille": 10**3, "million": 10**6, "millions": 10**6, "milliard": 10**9, "milliards": 10**9},
    "en": {"thousand": 10**3, "million": 10**6, "billion": 10**9},
}
# Ambigus seuls (article, adjectif, pronom) : lus seulement dans un nombre composé.
_AMBIGUOUS = {"fr": {"zéro", "un", "une", "neuf"}, "en": {"zero", "one"}}
_JOIN = {"fr": "et", "en": "and"}
_WORD = re.compile(r"[^\W\d_]+")
_GAP = re.compile(r"[\s\-\u2010\u2011]+")
_PERCENT = re.compile(r"[\s]*(?:%|pour[\s]*cent\b|pourcent\b|per[\s]*cent\b)", re.IGNORECASE)


def find_number_words(text: str, lang: Lang) -> Iterator[tuple[int, bool, tuple[int, int]]]:
    """Produit (valeur, pourcentage, position) pour chaque nombre en lettres."""
    units = {w: i for i, w in enumerate(_UNITS[lang].split())}
    if lang == "fr":
        units["une"] = 1
    tens, hundred, scale = _TENS[lang], _HUNDRED[lang], _SCALE[lang]
    tokens = [(m.group().lower(), m.start(), m.end()) for m in _WORD.finditer(text)]

    def adjacent(j: int) -> bool:
        return j < len(tokens) and bool(_GAP.fullmatch(text, tokens[j - 1][2], tokens[j][1]))

    i = 0
    while i < len(tokens):
        j, total, current, last = i, 0, 0, ""
        while j < len(tokens) and (j == i or adjacent(j)):
            word = tokens[j][0]
            if word == _JOIN[lang] and last:
                follows = tokens[j + 1][0] if adjacent(j + 1) else ""
                joins_tens = lang == "fr" and last == "tens" and follows in {"un", "une", "onze"}
                joins_hundred = lang == "en" and last == "hundred" and (follows in units or follows in tens)
                if not (joins_tens or joins_hundred):
                    break
            elif word in tens:
                if lang == "fr" and last == "unit" and word.startswith("vingt") and current % 100 == 4:
                    current += 76  # quatre-vingts
                elif last in {"unit", "tens"}:
                    break
                else:
                    current += tens[word]
                last = "tens"
            elif word in units:
                value = units[word]
                if last == "unit":
                    if not (lang == "fr" and 7 <= value <= 9 and current % 10 == 0 and current % 100 in {10, 70, 90}):
                        break
                elif last == "tens":
                    stacked = lang == "fr" and current % 100 in {60, 80}
                    if value >= 10 and not stacked:
                        break
                current += value
                last = "unit"
            elif word in hundred:
                before = text[: tokens[j][1]].rstrip().lower()
                if j == i and (lang == "en" or before.endswith("pour")):
                    break
                if last and (last != "unit" or current >= 20):
                    break
                current = max(current, 1) * 100
                last = "hundred"
            elif word in scale:
                if j == i and word != "mille":
                    break
                total += max(current, 1) * scale[word]
                current, last = 0, "scale"
            else:
                break
            j += 1
            if last and _PERCENT.match(text, tokens[j - 1][2]):
                break
        if j == i:
            i += 1
            continue
        if not (j == i + 1 and tokens[i][0] in _AMBIGUOUS[lang]):
            start, end = tokens[i][1], tokens[j - 1][2]
            pct = _PERCENT.match(text, end)
            yield total + current, bool(pct), (start, pct.end() if pct else end)
        i = j
