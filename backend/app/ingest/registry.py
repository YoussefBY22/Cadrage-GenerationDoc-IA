"""Choix du parseur par extension ET signature."""

from __future__ import annotations

import posixpath

from app.domain.documents import Block, ParsedDocument
from app.ingest.errors import ParseError, UnsupportedFormat
from app.ingest.parsers.common import guess_language, sha256_hex
from app.ingest.parsers.docx import parse_docx
from app.ingest.parsers.pdf import parse_pdf
from app.ingest.parsers.pptx import parse_pptx
from app.ingest.parsers.text import parse_text

MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "md": "text/markdown",
}
MAX_BYTES = 50 * 1024 * 1024


def _check_signature(ext: str, data: bytes) -> None:
    if ext == "pdf" and not data[:1024].lstrip().startswith(b"%PDF"):
        raise UnsupportedFormat("Signature PDF absente (%PDF)")
    if ext in {"docx", "pptx"} and not data.startswith(b"PK"):
        raise UnsupportedFormat(f"Signature ZIP absente pour {ext.upper()}")
    if ext in {"txt", "md"} and (data.startswith((b"%PDF", b"PK")) or b"\x00" in data[:4096]):
        raise UnsupportedFormat("Contenu binaire déguisé en texte")


def parse(filename: str, data: bytes) -> ParsedDocument:
    """Analyse un fichier. Lève UnsupportedFormat ou ParseError."""
    name = posixpath.basename(filename.replace("\\", "/"))
    ext = posixpath.splitext(name)[1].lower().lstrip(".")
    if ext not in MIME:
        raise UnsupportedFormat(f"Extension non prise en charge : .{ext}" if ext else "Extension absente")
    if not data:
        raise ParseError("Fichier vide")
    if len(data) > MAX_BYTES:
        raise ParseError("Fichier trop volumineux")
    _check_signature(ext, data)

    warnings: list[str] = []
    title: str | None = None
    blocks: list[Block]
    if ext == "pdf":
        blocks, warnings, title = parse_pdf(data)
    elif ext == "docx":
        blocks, title = parse_docx(data)
    elif ext == "pptx":
        blocks, title = parse_pptx(data)
    else:
        blocks = parse_text(data)
    if not blocks:
        warnings.append("Aucun texte extrait (document vide ou numérisé ?)")
    if title is None:
        title = next((b.text for b in blocks if b.kind == "heading"), None)
    sample = " ".join(b.text for b in blocks[:200])[:20000]
    return ParsedDocument(
        filename=name, mime=MIME[ext], sha256=sha256_hex(data), title=title,
        language=guess_language(sample), blocks=blocks, warnings=warnings,
    )
