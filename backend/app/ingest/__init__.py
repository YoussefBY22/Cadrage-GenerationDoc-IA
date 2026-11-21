"""Lecture de documents (PDF, DOCX, PPTX, TXT/MD) vers ParsedDocument."""

from app.ingest.errors import IngestError, ParseError, UnsupportedFormat
from app.ingest.registry import parse

__all__ = ["IngestError", "ParseError", "UnsupportedFormat", "parse"]
