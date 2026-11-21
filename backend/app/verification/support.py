"""Appui lexical : part des mots pleins d'une phrase présents dans ses sources."""

import re

from app.domain.ids import Lang
from app.retrieval.textnorm import tokenize


def _words(text: str, lang: Lang) -> list[str]:
    return [t for t in tokenize(text, lang) if not re.match(r"\d", t)]


def lexical_support(sentence: str, sources: list[str], lang: Lang = "fr") -> float:
    """Proportion (0..1) des mots pleins racinisés de la phrase trouvés dans les sources.

    Un indice, pas une preuve. Phrase sans mot plein : 1.0 ; aucune source : 0.0.
    """
    words = _words(sentence, lang)
    if not words:
        return 1.0
    pool: set[str] = set()
    for s in sources:
        pool.update(_words(s, lang))
    return sum(w in pool for w in words) / len(words)
