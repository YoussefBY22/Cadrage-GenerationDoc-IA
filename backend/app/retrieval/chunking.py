"""Découpage des documents en passages, selon la structure (08 §4.1)."""

import hashlib
import math

from app.domain.documents import Block, Chunk, ParsedDocument


def estimate_tokens(text: str) -> int:
    """Estimation sans tokeniseur : ceil(mots × 1,3)."""
    return math.ceil(len(text.split()) * 1.3)


def chunk_id(document_id: str, ordinal: int) -> str:
    digest = hashlib.sha1(f"{document_id}:{ordinal}".encode()).hexdigest()
    return f"chk_{digest[:12]}"


def indexed_text(chunk: Chunk) -> str:
    """Texte à indexer : titre de section préfixé (le texte affiché reste inchangé)."""
    if chunk.section_path:
        return f"{chunk.section_path[-1]} — {chunk.text}"
    return chunk.text


def _split_words(text: str, max_tokens: int) -> list[str]:
    """Coupe un texte trop long en morceaux de ≤ max_tokens (par mots)."""
    words = text.split()
    size = max(1, int(max_tokens / 1.3))
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size)]


def _split_lines(text: str, max_tokens: int) -> list[str]:
    """Coupe un tableau/une diapositive par lignes (par mots si une ligne est trop longue)."""
    parts: list[str] = []
    current: list[str] = []
    for line in text.split("\n"):
        if estimate_tokens(line) > max_tokens:
            if current:
                parts.append("\n".join(current))
                current = []
            parts.extend(_split_words(line, max_tokens))
            continue
        if current and estimate_tokens("\n".join([*current, line])) > max_tokens:
            parts.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        parts.append("\n".join(current))
    return parts


def _sections(blocks: list[Block]) -> list[tuple[tuple[str, ...], list[Block]]]:
    """Regroupe les blocs par section ; un titre est rattaché au contenu qui le suit."""
    groups: list[tuple[tuple[str, ...], list[Block]]] = []
    pending: list[Block] = []
    for block in blocks:
        if not block.text.strip():
            continue
        if block.kind == "heading":
            pending.append(block)
            continue
        if groups and groups[-1][0] == block.section_path and not pending:
            groups[-1][1].append(block)
        else:
            groups.append((block.section_path, [*pending, block]))
        pending = []
    if pending:  # titres sans contenu
        groups.append((pending[-1].section_path, pending))
    return groups


def chunk_document(
    doc: ParsedDocument,
    *,
    document_id: str,
    dossier_id: str,
    target_tokens: int = 350,
    max_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """Découpe un document : jamais à cheval sur deux sections, tableaux/diapos entiers
    (coupés par lignes seulement au-delà de max_tokens), chevauchement dans une section."""
    raw: list[tuple[str, tuple[str, ...], list[int]]] = []  # (texte, section, pages)
    room = max_tokens - overlap_tokens  # place pour le texte neuf, le chevauchement en plus
    keep_words = int(overlap_tokens / 1.3)

    def pages_of(blocks: list[Block]) -> list[int]:
        return [b.page for b in blocks if b.page is not None]

    for path, blocks in _sections(doc.blocks):
        current: list[Block] = []
        state = {"tokens": 0, "carry": ""}

        def flush(path=path, current=current, state=state):
            if not current:
                return
            text = "\n\n".join(b.text.strip() for b in current)
            body = f"{state['carry']}\n\n{text}" if state["carry"] else text
            raw.append((body, path, pages_of(current)))
            words = text.split()
            tail = words[-keep_words:] if keep_words and len(words) > keep_words else []
            state["carry"] = " ".join(tail)
            current.clear()
            state["tokens"] = 0

        for block in blocks:
            if block.kind in ("table", "slide"):
                flush()
                state["carry"] = ""
                parts = (
                    [block.text]
                    if estimate_tokens(block.text) <= max_tokens
                    else _split_lines(block.text, max_tokens)
                )
                for part in parts:
                    raw.append((part, path, pages_of([block])))
                continue
            pieces = (
                [block.text]
                if estimate_tokens(block.text) <= room
                else _split_words(block.text, room)
            )
            for piece in pieces:
                size = estimate_tokens(piece)
                if current and state["tokens"] + size > room:
                    flush()
                current.append(block.model_copy(update={"text": piece}))
                state["tokens"] += size
                if state["tokens"] >= target_tokens:
                    flush()
        flush()

    chunks: list[Chunk] = []
    for ordinal, (text, path, pages) in enumerate(raw):
        chunks.append(
            Chunk(
                id=chunk_id(document_id, ordinal),
                document_id=document_id,
                dossier_id=dossier_id,
                ordinal=ordinal,
                text=text,
                page_start=min(pages) if pages else None,
                page_end=max(pages) if pages else None,
                section_path=path,
                token_estimate=estimate_tokens(text),
            )
        )
    return chunks
