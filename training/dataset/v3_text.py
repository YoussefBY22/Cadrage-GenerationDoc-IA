"""Nettoyage du texte extrait de PDF et découpe d'un passage entre deux repères.

Un passage est du texte humain, recopié tel quel : seuls les retours à la ligne, les numéros de page
et de point, les puces et les espaces multiples sont normalisés. Aucune phrase n'est reformulée.
"""

from __future__ import annotations

import re
from functools import lru_cache

_PAGE = re.compile(r"^\s*\d{1,3}\s*$")
_BULLET = re.compile(r"^\s*[•\-–·]\s+")
_ITEM = re.compile(r"^([a-e]\)|Quand\s*\?|Recommandation n)")
_END = re.compile(r"[.:;?!)»]\s*$")
_POINT = re.compile(r"^\d{1,3} (?=[A-ZÀ-ÝŒ«])")


def normalize(raw: str) -> str:
    """Texte continu : un paragraphe par ligne, puces, numéros de page et de point retirés.

    Une ligne vide ne coupe un paragraphe que si le texte précédent est terminé (ponctuation finale) :
    ``pdftotext`` insère des lignes vides au milieu de certains paragraphes numérotés.
    """
    paras: list[str] = []
    cur: list[str] = []
    brk = False
    for ln in raw.splitlines():
        if _PAGE.match(ln):
            continue
        if not ln.strip():
            brk = bool(cur)
            continue
        text = _BULLET.sub("", ln).strip()
        starts_item = bool(_BULLET.match(ln)) or bool(_ITEM.match(text))
        if cur and (starts_item or (brk and _END.search(cur[-1]))):
            paras.append(" ".join(cur))
            cur = []
        brk = False
        cur.append(text)
    if cur:
        paras.append(" ".join(cur))
    return "\n".join(_POINT.sub("", re.sub(r"\s+", " ", p).strip()) for p in paras if p.strip())


def flat(text: str) -> str:
    """Forme comparable : espaces uniques, apostrophes droites."""
    return re.sub(r"\s+", " ", text.replace("’", "'").replace(" ", " ")).strip()


@lru_cache(maxsize=32)
def _prepared(text: str) -> tuple[str, str]:
    norm = normalize(text)
    return norm, norm.replace("’", "'").replace(" ", " ").replace(chr(10), " ")


def _key(anchor: str) -> str:
    return re.sub(r"\s+", " ", anchor.replace("’", "'").replace(" ", " ")).strip()


def between(text: str, start: str, end: str | None = None, *, include_end: bool = False,
            after: str | None = None) -> str:
    """Passage de ``start`` (inclus) jusqu'à ``end`` (exclu, sauf ``include_end``).

    Les repères se cherchent dans le texte déjà normalisé (les coupures de ligne du PDF n'y comptent pas).
    ``after`` : repère à dépasser d'abord, pour viser la bonne occurrence d'un intertitre qui se répète.
    """
    norm, key = _prepared(text)
    base = 0
    if after is not None:
        base = key.find(_key(after))
        if base < 0:
            raise ValueError(f"repère « after » introuvable : {after!r}")
    i = key.find(_key(start), base)
    if i < 0:
        raise ValueError(f"repère introuvable : {start!r}")
    if end is None:
        return norm[i:]
    e = _key(end)
    j = key.find(e, i + len(_key(start)))
    if j < 0:
        raise ValueError(f"repère de fin introuvable : {end!r}")
    return norm[i:j + (len(e) if include_end else 0)]
