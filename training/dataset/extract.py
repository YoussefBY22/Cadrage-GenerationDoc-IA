"""Extraction et nettoyage des documents publics (lot T4) : texte brut → paragraphes propres.

Aucun réseau. Entrées : `data/public/raw/<id>.txt|xhtml` décrites par `data/public/manifest.json`.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "public" / "manifest.json"
RAW = ROOT / "data" / "public" / "raw"
WORDS_PER_PAGE = 450  # estimation : les sources texte ne portent pas de pagination fiable

_SKIP = {"script", "style", "table", "head", "nav", "header", "footer"}
_BLOCKS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "br", "tr"}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
        elif tag in _BLOCKS:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in _BLOCKS:
            self.out.append("\n\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(raw: str) -> str:
    p = _Text()
    p.feed(raw)
    return "".join(p.out)


_TOC = re.compile(r"(\.\s?){4,}|(_\s?){4,}")
_PAGE = re.compile(r"^\s*(page\s*)?\d{1,4}(\s*/\s*\d+)?\s*$", re.I)
_URL_ONLY = re.compile(r"^\S+$")


def clean_text(text: str) -> list[str]:
    """Texte brut → liste de paragraphes (>= 8 mots), sans table des matières ni en-têtes répétés."""
    text = unicodedata.normalize("NFC", text).replace(chr(173), "").replace(chr(13), "")
    text = re.sub("[" + chr(160) + chr(8239) + "]", " ", text)
    text = re.sub("[  ]", " ", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # césure en fin de ligne
    text = re.sub(r"\n{3,}", "\n\n", text)
    blocks = [re.sub(r"\s*\n\s*", " ", b).strip() for b in text.split("\n\n")]
    repeated = {b for b, n in Counter(blocks).items() if n >= 4 and len(b) < 120}
    out = []
    for b in blocks:
        b = re.sub(r"\s+", " ", b)
        words = b.split()
        if len(words) < 8 or b in repeated or _TOC.search(b) or _PAGE.match(b) or _URL_ONLY.match(b):
            continue
        letters = sum(ch.isalpha() for ch in b)
        if letters < 0.55 * len(b):  # tableaux aplatis, numéros
            continue
        out.append(b)
    return out


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST.read_text("utf-8"))["documents"]


def read_document(entry: dict, raw_dir: Path = RAW) -> list[str] | None:
    """Paragraphes d'un document du manifeste, ou None si le fichier n'est pas téléchargé."""
    path = raw_dir / f"{entry['id']}.{entry['format']}"
    if not path.exists():
        return None
    raw = path.read_text("utf-8", errors="replace")
    return clean_text(html_to_text(raw) if entry["format"] == "xhtml" else raw)


_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÝÉÈ0-9“\"(])")


def sentences(paragraph: str) -> list[str]:
    return [s.strip() for s in _SENT.split(paragraph) if s.strip()]


def chunk_paragraphs(paras: list[str], max_words: int = 170) -> list[str]:
    """Regroupe des paragraphes consécutifs jusqu'à `max_words` mots (coupe sur les phrases au besoin)."""
    chunks, cur, n = [], [], 0
    pieces = []
    for p in paras:
        pieces += [p] if len(p.split()) <= max_words else _split_long(p, max_words)
    for p in pieces:
        w = len(p.split())
        if cur and n + w > max_words:
            chunks.append(" ".join(cur))
            cur, n = [], 0
        cur.append(p)
        n += w
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _split_long(p: str, max_words: int) -> list[str]:
    out, cur, n = [], [], 0
    for s in sentences(p):
        w = len(s.split())
        if cur and n + w > max_words:
            out.append(" ".join(cur))
            cur, n = [], 0
        cur.append(s)
        n += w
    if cur:
        out.append(" ".join(cur))
    return out
