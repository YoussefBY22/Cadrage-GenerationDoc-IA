"""Extraction et normalisation des nombres (FR/EN) d'une phrase."""

import re
from dataclasses import dataclass
from decimal import Decimal

from app.domain.ids import Lang

# espace, insécable, fine insécable, fine
_SP = "    "

# Numéro de liste ou de section en début de phrase : « 1. », « 2) », « 2.1 Contexte ».
_LEAD = re.compile(
    rf"^(?P<pre>[\s\-•*]*)(?P<num>\d{{1,2}}(?:\.\d+)*[.)]|\d{{1,2}}(?:\.\d+)+(?=[{_SP}]+[A-ZÀ-Ý]))"
    rf"(?=[{_SP}]+(?!(?:Md|M|Mille|Millions?|Milliards?|Pour)\b))"
)

_SUFFIX = (
    rf"(?P<suf>[{_SP}]*(?:%|(?i:pour[{_SP}]*cent|pourcent|percent)|(?i:milliards?)|Md|(?i:millions?)"
    r"|(?i:mille)|M|k)(?![^\W\d_]))"
)
_NUMBER = (
    r"(?<![^\W\d_])(?P<num>"
    r"\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?"  # 1,250,000.5 (EN)
    r"|\d{1,3}(?:\.\d{3}){2,}(?:,\d+)?"  # 1.250.000,5 (FR)
    rf"|\d{{1,3}}(?:[{_SP}]\d{{3}})+(?:[.,]\d+)?"  # 1 250,5
    r"|\d+(?:[.,]\d+)?)"
)
_RE = re.compile(_NUMBER + r"(?:" + _SUFFIX + r")?")

_MULT = {
    "k": 10**3, "mille": 10**3, "m": 10**6, "million": 10**6, "millions": 10**6,
    "md": 10**9, "milliard": 10**9, "milliards": 10**9,
}


@dataclass(frozen=True)
class NumberMention:
    raw: str
    value: Decimal
    is_percent: bool
    span: tuple[int, int]


def _to_decimal(num: str, lang: Lang) -> Decimal:
    num = re.sub(rf"[{_SP}]", "", num)
    if num.count(",") > 1:  # virgules = milliers (EN)
        num = num.replace(",", "")
    elif num.count(".") > 1:  # points = milliers (FR)
        num = num.replace(".", "").replace(",", ".")
    elif "," in num and "." in num:
        if num.rfind(".") > num.rfind(","):
            num = num.replace(",", "")
        else:
            num = num.replace(".", "").replace(",", ".")
    elif "," in num:
        head, tail = num.split(",")
        num = head + tail if (lang == "en" and len(tail) == 3 and len(head) <= 3) else head + "." + tail
    return Decimal(num)


def extract_numbers(text: str, lang: Lang = "fr") -> list[NumberMention]:
    """Liste les nombres de ``text`` (valeur normalisée, statut pourcentage, position)."""
    masked = text
    lead = _LEAD.match(text)
    if lead:
        end = lead.end("num")
        masked = " " * end + text[end:]
    out: list[NumberMention] = []
    for m in _RE.finditer(masked):
        value = _to_decimal(m.group("num"), lang)
        suf = (m.group("suf") or "").strip()
        key = re.sub(r"\s+", "", suf.lower())
        is_percent = key == "%" or key.startswith("pourcent") or key in {"percent"}
        if suf and not is_percent:
            mult = _MULT.get(key)
            if mult:
                value = value * mult
        out.append(NumberMention(m.group(0).strip(), value.normalize() + 0, is_percent, m.span()))
    return out
