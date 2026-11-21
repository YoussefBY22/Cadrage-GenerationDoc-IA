"""Parseur TXT / Markdown."""

from __future__ import annotations

import re

from app.domain.documents import Block
from app.ingest.errors import ParseError
from app.ingest.parsers.common import SectionTracker, clean, is_numbered_heading

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
_LIST = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def parse_text(data: bytes) -> list[Block]:
    try:
        raw = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            raw = data.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise ParseError("Texte illisible (encodage inconnu)") from exc
    tracker = SectionTracker()
    blocks: list[Block] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            text = clean("\n".join(para))
            kind = "list" if all(_LIST.match(p) for p in para) else "paragraph"
            if text:
                blocks.append(Block(text=text, page=None, section_path=tracker.path, kind=kind))
            para.clear()

    for line in raw.splitlines():
        md = _MD_HEADING.match(line.strip())
        num = None if md else is_numbered_heading(line)
        if md or num:
            flush()
            title, level = (clean(md.group(2)), len(md.group(1))) if md else (clean(num[0]), num[1])
            blocks.append(Block(text=title, page=None, section_path=tracker.push(level, title), kind="heading"))
        elif not line.strip():
            flush()
        else:
            para.append(line.strip())
    flush()
    return blocks
