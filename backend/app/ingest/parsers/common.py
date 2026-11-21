"""Utilitaires partagés par les parseurs."""

from __future__ import annotations

import hashlib
import re
import unicodedata

from app.domain.ids import Lang

# Titre numéroté : « 2 Titre », « 2.1 Gouvernance », « 2.1. Gouvernance », « 3) Titre »
NUMBERED_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})[.)]?\s+(\S.{0,118})$")

_FR = {"le", "la", "les", "des", "une", "est", "dans", "pour", "que", "avec", "sur", "pas", "qui", "sont", "du", "et"}
_EN = {"the", "and", "of", "to", "is", "in", "for", "that", "with", "on", "are", "this", "be", "as", "by"}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guess_language(text: str) -> Lang | None:
    """Devine fr/en par comptage de mots vides ; None si indécidable."""
    words = re.findall(r"[a-zà-ÿ']+", text.lower())
    fr = sum(w in _FR for w in words)
    en = sum(w in _EN for w in words)
    if fr + en < 3 or fr == en:
        return None
    return "fr" if fr > en else "en"


def is_numbered_heading(line: str) -> tuple[str, int] | None:
    """Renvoie (ligne, niveau) si la ligne ressemble à un titre numéroté court."""
    line = line.strip()
    m = NUMBERED_HEADING.match(line)
    if not m:
        return None
    if line.endswith((".", ";", ",")) or len(line.split()) > 14:
        return None
    if re.fullmatch(r"[\d\s.,%€$]+", m.group(2)) or not re.match(r"[A-Za-zÀ-ÿ]", m.group(2)):
        return None
    return line, m.group(1).count(".") + 1


class SectionTracker:
    """Maintient le chemin de sections courant selon le niveau des titres."""

    def __init__(self) -> None:
        self._stack: list[tuple[int, str]] = []

    def push(self, level: int, title: str) -> tuple[str, ...]:
        while self._stack and self._stack[-1][0] >= level:
            self._stack.pop()
        self._stack.append((level, title))
        return self.path

    @property
    def path(self) -> tuple[str, ...]:
        return tuple(t for _, t in self._stack)


def clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\x00", "")
    return re.sub(r"[ \t]+", " ", text).strip()
