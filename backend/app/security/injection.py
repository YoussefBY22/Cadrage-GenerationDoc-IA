"""Détection de consignes cachées (injection de prompt), motifs FR/EN."""

from __future__ import annotations

import re
import unicodedata

from app.security.sanitize import ZERO_WIDTH

IGNORE_INSTRUCTIONS = "IGNORE_INSTRUCTIONS"
ROLE_OVERRIDE = "ROLE_OVERRIDE"
DELIMITER_SPOOF = "DELIMITER_SPOOF"
HIDDEN_TEXT = "HIDDEN_TEXT"
EXFIL_URL = "EXFIL_URL"

_QUAL = (
    r"(?:(?:toutes?|tous|all|any|the|your|previous|prior|above|earlier|former|those|these|precedentes?|"
    r"precedents?|anterieures?|ci-dessus|les|des|vos|tes|mes|ces|ses|leurs?|de|du|a)\s+){0,4}"
)
_OBJ = r"(?:instructions?|consignes?|directives?|regles?|prompts?|rules?|guidelines?|commandes?|orders?)"

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (IGNORE_INSTRUCTIONS, re.compile(
        rf"\b(?:ignor\w*|oublie\w*|neglige\w*|desobei\w*|disregard|forget|override|bypass)\s+{_QUAL}{_OBJ}", re.IGNORECASE)),
    (IGNORE_INSTRUCTIONS, re.compile(
        rf"\b(?:ne\s+suis\s+pas|ne\s+tiens\s+pas\s+compte\s+d\w*|do\s+not\s+follow|don'?t\s+follow)\s+{_QUAL}{_OBJ}", re.IGNORECASE)),
    (IGNORE_INSTRUCTIONS, re.compile(r"\b(?:nouvelles?|new)\s+(?:instructions?|consignes?)\s*:", re.IGNORECASE)),
    (ROLE_OVERRIDE, re.compile(r"\btu\s+es\s+(?:desormais|maintenant|a\s+present)\b", re.IGNORECASE)),
    (ROLE_OVERRIDE, re.compile(
        r"\b(?:you\s+are\s+now|from\s+now\s+on,?\s+you|pretend\s+(?:to\s+be|you\s+are)|"
        r"a\s+partir\s+de\s+maintenant,?\s+tu|joue\s+le\s+role\s+de)\b", re.IGNORECASE)),
    (ROLE_OVERRIDE, re.compile(r"(?:^|[\n\r.>\]]\s*|\s{2,})(?:system|assistant|developer|systeme)\s*:", re.IGNORECASE)),
    (ROLE_OVERRIDE, re.compile(
        r"\[\s*/?\s*(?:inst|system|sys)\s*\]|<\|(?:im_start|im_end|system|assistant)\|>|###\s*(?:system|instruction)",
        re.IGNORECASE)),
    (DELIMITER_SPOOF, re.compile(r"<<|>>|\bnonce\s*=", re.IGNORECASE)),
    (EXFIL_URL, re.compile(r"https?://[^\s)\"'>]*\?[^\s)\"'>]*=", re.IGNORECASE)),
    (EXFIL_URL, re.compile(r"!\[[^\]]*\]\(\s*https?://", re.IGNORECASE)),
]


def _fold(text: str) -> str:
    """Minuscules sans accents, largeur nulle retirée."""
    text = unicodedata.normalize("NFKD", text.translate(ZERO_WIDTH))
    return "".join(c for c in text if not unicodedata.combining(c))


def scan(text: str) -> list[str]:
    """Renvoie les codes détectés (sans doublon, ordre stable)."""
    found: list[str] = []
    if sum(ord(c) in ZERO_WIDTH for c in text) >= 3:
        found.append(HIDDEN_TEXT)
    folded = _fold(text)
    for code, pattern in _PATTERNS:
        if code not in found and pattern.search(folded):
            found.append(code)
    return found
