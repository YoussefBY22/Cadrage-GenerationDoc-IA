"""Ingestion d'un fichier : lecture, découpage, détection d'injection, vectorisation, stockage."""

import logging
from pathlib import Path

from sqlalchemy import select

from app.config import Settings, get_settings
from app.domain.workflow import CurrentUser
from app.ingest import ParseError, UnsupportedFormat, parse
from app.llm.base import LLMProvider
from app.retrieval.chunking import chunk_document, indexed_text
from app.security import injection
from app.storage import DuplicateDocumentError
from app.storage import schema as s

log = logging.getLogger("app.ingestion")

BATCH = 32
PASSAGE_PREFIX = "passage: "  # préfixe des modèles type e5 (08 §3) ; surchargeable par la config


class IngestionError(Exception):
    """Erreur métier avec son code HTTP (413, 409, 415, 422)."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def ingest(repo, provider: LLMProvider, dossier_id: str, filename: str, data: bytes,
           user: CurrentUser, *, search=None, settings: Settings | None = None) -> dict:
    """Renvoie {document_id, chunks, alerts} (alerts = nombre de passages signalés)."""
    settings = settings or get_settings()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise IngestionError(413, "FILE_TOO_LARGE", f"Fichier > {settings.max_upload_mb} Mo")
    try:
        parsed = parse(filename, data)
    except UnsupportedFormat as exc:
        raise IngestionError(415, "UNSUPPORTED_FORMAT", str(exc)) from exc
    except ParseError as exc:
        raise IngestionError(422, "PARSE_ERROR", str(exc)) from exc
    if repo.find_document_by_sha(dossier_id, parsed.sha256):
        raise IngestionError(409, "DUPLICATE_DOCUMENT", "Document déjà importé dans ce dossier")

    folder = Path(settings.upload_dir) / dossier_id
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / parsed.sha256
    stored.write_bytes(data)
    try:
        doc_id = repo.add_document(dossier_id, parsed, str(stored))
    except DuplicateDocumentError as exc:
        raise IngestionError(
            409, "DUPLICATE_DOCUMENT", "Document déjà importé dans ce dossier") from exc

    chunks = chunk_document(parsed, document_id=doc_id, dossier_id=dossier_id)
    chunks = [c.model_copy(update={"injection_flags": flags}) if (flags := injection.scan(c.text))
              else c for c in chunks]
    prefix = getattr(settings, "embedding_passage_prefix", PASSAGE_PREFIX)
    texts = [prefix + indexed_text(c) for c in chunks]
    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        vectors += provider.embed(texts[i:i + BATCH])
    repo.add_chunks(chunks, vectors, provider.name)

    alerts = 0
    for c in chunks:
        if c.injection_flags:
            repo.record_alert(c.id, c.injection_flags)
            alerts += 1
    repo.audit(user.id, "document.ingest", "document", doc_id,
               {"chunks": len(chunks), "alerts": alerts, "sha256": parsed.sha256})
    if search is not None:
        search.invalidate(dossier_id)
    log.info("ingested", extra={"chunks": len(chunks), "alerts": alerts})
    return {"document_id": doc_id, "chunks": len(chunks), "alerts": alerts}


# --- lectures (SqlRepository : accès direct aux tables, la Repository n'expose pas ces lectures)
_DOC_COLS = ("id", "dossier_id", "filename", "mime", "sha256", "title", "language", "pages",
             "created_at")


def _doc(row) -> dict:
    d = {k: row._mapping[k] for k in _DOC_COLS}
    d["created_at"] = d["created_at"].isoformat() if d["created_at"] else None
    return d


def list_documents(repo, dossier_id: str) -> list[dict]:
    stmt = (select(*[s.documents.c[k] for k in _DOC_COLS])
            .where(s.documents.c.dossier_id == dossier_id)
            .order_by(s.documents.c.created_at, s.documents.c.id))
    with repo.engine.connect() as c:
        return [_doc(r) for r in c.execute(stmt)]


def get_document(repo, document_id: str) -> dict | None:
    stmt = select(*[s.documents.c[k] for k in _DOC_COLS]).where(s.documents.c.id == document_id)
    with repo.engine.connect() as c:
        row = c.execute(stmt).first()
    return _doc(row) if row else None


def get_chunk(repo, chunk_id: str) -> dict | None:
    """Passage avec son document ; le contrôle d'appartenance se fait sur `dossier_id`."""
    stmt = (select(s.chunks, s.documents.c.filename).join(
        s.documents, s.documents.c.id == s.chunks.c.document_id)
        .where(s.chunks.c.id == chunk_id))
    with repo.engine.connect() as c:
        row = c.execute(stmt).first()
    if not row:
        return None
    m = row._mapping
    return {"id": m["id"], "dossier_id": m["dossier_id"], "document_id": m["document_id"],
            "document": m["filename"], "text": m["text"], "page_start": m["page_start"],
            "page_end": m["page_end"], "section_path": list(m["section_path"] or []),
            "injection_flags": list(m["injection_flags"] or [])}
