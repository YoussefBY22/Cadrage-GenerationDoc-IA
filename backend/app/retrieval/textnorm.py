"""Normalisation et segmentation en jetons pour BM25 (minuscules, sans accents, racinisation)."""

import re
import unicodedata
from functools import lru_cache

import snowballstemmer

from app.domain.ids import Lang

STOPWORDS_FR = frozenset(
    [
        "a",
        "au",
        "aux",
        "avec",
        "ce",
        "ces",
        "cet",
        "cette",
        "dans",
        "de",
        "des",
        "du",
        "elle",
        "elles",
        "en",
        "est",
        "et",
        "eu",
        "il",
        "ils",
        "je",
        "la",
        "le",
        "les",
        "leur",
        "leurs",
        "lui",
        "ma",
        "mais",
        "me",
        "mes",
        "moi",
        "mon",
        "ne",
        "nos",
        "notre",
        "nous",
        "on",
        "ou",
        "par",
        "pas",
        "pour",
        "qu",
        "que",
        "qui",
        "sa",
        "se",
        "ses",
        "son",
        "sur",
        "ta",
        "te",
        "tes",
        "toi",
        "ton",
        "tu",
        "un",
        "une",
        "vos",
        "votre",
        "vous",
        "y",
        "ete",
        "etre",
        "sont",
        "sera",
        "ont",
        "avoir",
        "fait",
        "plus",
        "comme",
        "si",
        "ni",
        "aussi",
        "donc",
        "car",
        "entre",
        "sans",
        "sous",
        "vers",
        "chez",
        "tout",
        "tous",
        "toute",
        "toutes",
    ]
)
STOPWORDS_EN = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "his",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "she",
        "so",
        "such",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "which",
        "who",
        "will",
        "with",
        "you",
        "your",
    ]
)
STOPWORDS = STOPWORDS_FR | STOPWORDS_EN

_SPACES = r"[    ]"
# « 1 250 » ou « 1 250 000 » -> « 1250 » ; groupes de 3 chiffres exactement
_THOUSANDS = re.compile(rf"(?<!\d)(\d{{1,3}})((?:{_SPACES}\d{{3}})+)(?!\d)")
_PERCENT = re.compile(rf"(\d){_SPACES}*%")
_TOKEN = re.compile(r"\d+(?:[.,]\d+)?%?|[^\W\d_]+")


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@lru_cache(maxsize=2)
def _stemmer(lang: str):
    return snowballstemmer.stemmer("french" if lang == "fr" else "english")


def tokenize(text: str, lang: Lang = "fr") -> list[str]:
    """Découpe en jetons : minuscules, sans accents, sans mots vides, racinisés.

    Les nombres sont conservés tels quels (« 1 250 » -> « 1250 », « 15 % » -> « 15% »).
    """
    text = _strip_accents(text.lower())
    text = _THOUSANDS.sub(lambda m: m.group(1) + re.sub(_SPACES, "", m.group(2)), text)
    text = _PERCENT.sub(r"\1%", text)
    stem = _stemmer(lang)
    tokens: list[str] = []
    for raw in _TOKEN.findall(text):
        if raw[0].isdigit():
            tokens.append(raw)
        elif raw not in STOPWORDS and len(raw) > 1:
            tokens.append(stem.stemWord(raw))
    return tokens
