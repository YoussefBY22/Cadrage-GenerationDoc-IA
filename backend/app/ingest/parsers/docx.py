"""Parseur DOCX (python-docx) : styles Heading/Titre, tableaux, listes."""

from __future__ import annotations

import io
import re

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.domain.documents import Block
from app.ingest.errors import ParseError
from app.ingest.parsers.common import SectionTracker, clean

_HEADING = re.compile(r"^(?:heading|titre)\s*(\d)$", re.IGNORECASE)


def parse_docx(data: bytes) -> tuple[list[Block], str | None]:
    try:
        doc = Document(io.BytesIO(data))
        body = list(doc.element.body.iterchildren())
    except Exception as exc:
        raise ParseError("DOCX illisible ou corrompu") from exc
    tracker = SectionTracker()
    blocks: list[Block] = []
    title: str | None = None
    for child in body:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, doc)
            text = clean(p.text)
            if not text:
                continue
            style = p.style.name if p.style is not None else ""
            m = _HEADING.match(style.strip())
            if style.strip().lower() in {"title", "titre"} and title is None:
                title = text
            if m:
                blocks.append(
                    Block(text=text, page=None, section_path=tracker.push(int(m.group(1)), text), kind="heading")
                )
            else:
                kind = "list" if "list" in style.lower() or "liste" in style.lower() else "paragraph"
                blocks.append(Block(text=text, page=None, section_path=tracker.path, kind=kind))
        elif tag == "tbl":
            table = Table(child, doc)
            rows = []
            for row in table.rows:
                cells: list[str] = []
                for cell in row.cells:
                    c = clean(cell.text)
                    if not cells or cells[-1] != c or not c:  # cellules fusionnées répétées
                        cells.append(c)
                rows.append(" | ".join(cells))
            text = "\n".join(r for r in rows if r.strip(" |"))
            if text:
                blocks.append(Block(text=text, page=None, section_path=tracker.path, kind="table"))
    if title is None:
        try:
            title = doc.core_properties.title or None
        except Exception:  # noqa: BLE001
            title = None
    return blocks, title
