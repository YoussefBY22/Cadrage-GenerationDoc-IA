"""Parseur PPTX (python-pptx) : une diapositive = une page, kind « slide »."""

from __future__ import annotations

import io

from pptx import Presentation

from app.domain.documents import Block
from app.ingest.errors import ParseError
from app.ingest.parsers.common import clean


def _shape_texts(shapes) -> list[str]:
    out: list[str] = []
    for shape in shapes:
        if shape.shape_type == 6:  # groupe de formes
            out.extend(_shape_texts(shape.shapes))
        elif getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                line = " | ".join(clean(c.text) for c in row.cells)
                if line.strip(" |"):
                    out.append(line)
        elif getattr(shape, "has_text_frame", False) and shape.has_text_frame:
            t = clean(shape.text_frame.text)
            if t:
                out.append(t)
    return out


def parse_pptx(data: bytes) -> tuple[list[Block], str | None]:
    try:
        prs = Presentation(io.BytesIO(data))
        slides = list(prs.slides)
    except Exception as exc:
        raise ParseError("PPTX illisible ou corrompu") from exc
    blocks: list[Block] = []
    first_title: str | None = None
    for number, slide in enumerate(slides, start=1):
        ts = slide.shapes.title
        title = clean(ts.text_frame.text) if ts is not None and ts.has_text_frame else ""
        parts = [t for t in _shape_texts(slide.shapes) if t != title]
        if slide.has_notes_slide:
            notes = clean(slide.notes_slide.notes_text_frame.text)
            if notes:
                parts.append(f"Notes : {notes}")
        text = "\n".join(([title] if title else []) + parts)
        if not text.strip():
            continue
        first_title = first_title or title or None
        blocks.append(Block(text=text, page=number, section_path=(title,) if title else (), kind="slide"))
    return blocks, first_title
