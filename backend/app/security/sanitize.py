"""Neutralisation du texte client avant insertion dans un prompt."""

from __future__ import annotations

import re
import unicodedata

ZERO_WIDTH = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF, 0x00AD, 0x180E]
    + list(range(0x202A, 0x202F))
    + list(range(0x2066, 0x206A))
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_REPEAT = re.compile(r"(.)\1{19,}", re.DOTALL)


def neutralize(text: str, nonce: str) -> str:
    """Retire « << », « >> », le nonce, contrôles et largeur nulle ; tronque les répétitions. Idempotent."""
    text = unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH)
    text = _CONTROL.sub("", text)
    previous = None
    while previous != text:  # retirer « << » peut recomposer une séquence (« <<< »)
        previous = text
        text = text.replace("<<", "").replace(">>", "")
        if nonce:
            text = text.replace(nonce, "")
    return _REPEAT.sub(lambda m: m.group(1) * 20, text)
