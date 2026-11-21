"""Documents lus, blocs et passages indexés."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .ids import Lang


class Block(BaseModel):
    """Sortie des parseurs : un bloc de texte localisé."""

    model_config = ConfigDict(frozen=True)

    text: str
    page: int | None  # 1-based ; None si le format n'a pas de pages (txt, docx)
    section_path: tuple[str, ...] = ()
    kind: Literal["heading", "paragraph", "list", "table", "slide"] = "paragraph"


class ParsedDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    filename: str
    mime: str
    sha256: str
    title: str | None
    language: Lang | None
    blocks: list[Block]
    warnings: list[str] = []


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    document_id: str
    dossier_id: str
    ordinal: int
    text: str
    page_start: int | None
    page_end: int | None
    section_path: tuple[str, ...]
    token_estimate: int
    injection_flags: list[str] = []  # codes de security.injection
