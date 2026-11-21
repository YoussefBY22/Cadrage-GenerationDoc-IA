"""Parseur PDF (pypdf) : un Block par paragraphe, page 1-based."""

from __future__ import annotations

import io

from pypdf import PdfReader

from app.domain.documents import Block
from app.ingest.errors import ParseError
from app.ingest.parsers.common import SectionTracker, clean, is_numbered_heading

MIN_FONT_PT = 2.0


def parse_pdf(data: bytes) -> tuple[list[Block], list[str], str | None]:
    """Renvoie (blocs, avertissements, titre des métadonnées)."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ParseError("PDF chiffré")
        pages = list(reader.pages)
    except ParseError:
        raise
    except Exception as exc:  # pypdf lève des types variés sur fichier corrompu
        raise ParseError("PDF illisible ou corrompu") from exc

    tracker = SectionTracker()
    blocks: list[Block] = []
    warnings: list[str] = []
    for number, page in enumerate(pages, start=1):
        tiny: list[float] = []

        def visitor(text, cm, tm, font_dict, font_size, _tiny=tiny):
            scale = abs(tm[3]) if tm and len(tm) > 3 and tm[3] else 1.0
            size = abs(font_size or 0) * scale
            if text.strip() and 0 < size < MIN_FONT_PT:
                _tiny.append(size)

        try:
            text = page.extract_text(visitor_text=visitor) or ""
        except Exception as exc:
            raise ParseError(f"Page {number} illisible") from exc
        if tiny:
            warnings.append(f"HIDDEN_TEXT: texte de police < {MIN_FONT_PT:g} pt page {number}")
        para: list[str] = []

        def flush(_page: int = number, _para: list[str] = para) -> None:
            if _para:
                t = clean(" ".join(_para))
                if t:
                    blocks.append(Block(text=t, page=_page, section_path=tracker.path, kind="paragraph"))
                _para.clear()

        for line in text.splitlines():
            line = line.strip()
            if not line:
                flush()
                continue
            head = is_numbered_heading(line)
            if head:
                flush()
                title, level = clean(head[0]), head[1]
                blocks.append(Block(text=title, page=number, section_path=tracker.push(level, title), kind="heading"))
            else:
                para.append(line)
        flush()
    title = None
    try:
        title = (reader.metadata.title or None) if reader.metadata else None
    except Exception:  # noqa: BLE001
        title = None
    return blocks, warnings, title
