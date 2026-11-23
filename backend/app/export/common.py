"""Éléments communs aux exports : citations [n], table des sources, empreinte, garde d'approbation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import insert, select

from app.domain.documents import Chunk
from app.domain.generation import DeliverableContent
from app.domain.ids import new_id
from app.storage import schema as s

EXCERPT_CHARS = 200

# Libellés des exports, par langue du livrable (le contenu suit la langue choisie, pas celle du dossier).
LABELS: dict[str, dict[str, str]] = {
    "fr": {
        "footer": "Version {version} · SHA-256 {sha} · Approuvé par {approver} le {date}",
        "insufficient": "Éléments insuffisants : {detail}", "unspecified": "non précisé",
        "initiatives": "Initiatives priorisées", "matrix": "Matrice constats → initiatives",
        "rank": "Rang", "wave": "Vague", "score": "Score", "initiative": "Initiative",
        "finding": "Constat", "sources": "Sources", "document": "Document", "page": "Page",
        "section": "Section", "excerpt": "Extrait", "summary": "Synthèse",
        "wave_slide": "Vague {wave}", "score_inline": "score {score}",
        "gantt": "Calendrier (Gantt, semaines)", "weeks": "sem.",
        "gantt_order": "Ordre d'exécution", "no_dates": "Durées non saisies : ordre seulement, aucune date.",
        "priority_matrix": "Matrice de priorité ({x} × {y})", "unknown": "inconnu",
        "decision_by": "Décision de {author}, {date}",
    },
    "en": {
        "footer": "Version {version} · SHA-256 {sha} · Approved by {approver} on {date}",
        "insufficient": "Insufficient evidence: {detail}", "unspecified": "not specified",
        "initiatives": "Prioritised initiatives", "matrix": "Findings → initiatives matrix",
        "rank": "Rank", "wave": "Wave", "score": "Score", "initiative": "Initiative",
        "finding": "Finding", "sources": "Sources", "document": "Document", "page": "Page",
        "section": "Section", "excerpt": "Excerpt", "summary": "Executive summary",
        "wave_slide": "Wave {wave}", "score_inline": "score {score}",
        "gantt": "Timeline (Gantt, weeks)", "weeks": "wk.",
        "gantt_order": "Execution order", "no_dates": "Durations not entered: order only, no dates.",
        "priority_matrix": "Priority matrix ({x} × {y})", "unknown": "unknown",
        "decision_by": "Decision by {author}, {date}",
    },
}


def labels(lang: str) -> dict[str, str]:
    return LABELS.get(lang, LABELS["fr"])


class ExportForbidden(Exception):
    """Le livrable n'est pas approuvé, ou ses preuves ne tiennent plus."""


class ExportUnavailable(Exception):
    """Format indisponible (ex. LibreOffice absent) ; la route répond 501."""


@dataclass(frozen=True)
class SourceEntry:
    n: int
    document: str
    page: str
    section: str
    excerpt: str


@dataclass(frozen=True)
class ExportSentence:
    text: str
    numbers: list[int]

    @property
    def rendered(self) -> str:
        return self.text + "".join(f" [{n}]" for n in self.numbers)


@dataclass(frozen=True)
class ExportSection:
    key: str
    title: str
    status: str
    sentences: list[ExportSentence]
    missing_evidence: str | None = None


@dataclass(frozen=True)
class ExportData:
    deliverable_id: str
    version: int
    title: str
    content: DeliverableContent
    sections: list[ExportSection]
    sources: list[SourceEntry]
    sha256: str
    approver: str
    approved_at: str

    @property
    def footer(self) -> str:
        return labels(self.content.language)["footer"].format(
            version=self.version, sha=self.sha256[:16], approver=self.approver, date=self.approved_at)

    @property
    def labels(self) -> dict[str, str]:
        return labels(self.content.language)


def content_sha256(content: DeliverableContent) -> str:
    """Empreinte SHA-256 du contenu (même calcul que le dépôt)."""
    payload = content.model_dump(mode="json")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _excerpt(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= EXCERPT_CHARS else flat[: EXCERPT_CHARS - 1].rstrip() + "…"


def _pages(c: Chunk) -> str:
    if c.page_start is None:
        return "—"
    if c.page_end in (None, c.page_start):
        return str(c.page_start)
    return f"{c.page_start}-{c.page_end}"


@dataclass(frozen=True)
class ExportDecision:
    """Décision confirmée citée : l'export la montre comme « décision de <auteur>, <date> »."""

    text: str
    category: str
    author: str
    date: str


def build_export_data(
    content: DeliverableContent,
    chunks: dict[str, Chunk],
    doc_names: dict[str, str],
    *,
    deliverable_id: str,
    version: int,
    approver: str,
    approved_at: str,
    titles: dict[str, str] | None = None,
    title: str = "",
    decisions: dict[str, ExportDecision] | None = None,
) -> ExportData:
    """Numérote les citations par ordre d'apparition et construit la table des sources."""
    titles = titles or {}
    numbers: dict[str, int] = {}
    sources: list[SourceEntry] = []
    sections: list[ExportSection] = []
    for sec in content.sections:
        sents: list[ExportSentence] = []
        for sent in sec.sentences:
            nums: list[int] = []
            for cid in sent.source_ids:
                chunk = chunks.get(cid)
                if chunk is None:  # jamais d'effacement silencieux d'une citation
                    raise ExportForbidden(
                        f"citation invalide dans « {sec.section_key} » : passage {cid} introuvable "
                        "dans ce dossier ; corrigez la section avant d'exporter")
                if cid not in numbers:
                    numbers[cid] = len(numbers) + 1
                    sources.append(
                        SourceEntry(
                            n=numbers[cid],
                            document=doc_names.get(chunk.document_id, chunk.document_id),
                            page=_pages(chunk),
                            section=" > ".join(chunk.section_path) or "—",
                            excerpt=_excerpt(chunk.text),
                        )
                    )
                if numbers[cid] not in nums:
                    nums.append(numbers[cid])
            for did in sent.decision_ids:
                dec = (decisions or {}).get(did)
                if dec is None:
                    raise ExportForbidden(
                        f"citation invalide dans « {sec.section_key} » : décision {did} "
                        "introuvable ou non confirmée ; corrigez la section avant d'exporter")
                key = "decision:" + did
                if key not in numbers:
                    numbers[key] = len(numbers) + 1
                    sources.append(SourceEntry(
                        n=numbers[key],
                        document=labels(content.language)["decision_by"].format(
                            author=dec.author, date=dec.date),
                        page="—", section=dec.category, excerpt=_excerpt(dec.text)))
                if numbers[key] not in nums:
                    nums.append(numbers[key])
            sents.append(ExportSentence(sent.text, nums))
        sections.append(
            ExportSection(sec.section_key, titles.get(sec.section_key, sec.section_key), sec.status, sents,
                          sec.missing_evidence)
        )
    return ExportData(
        deliverable_id=deliverable_id,
        version=version,
        title=title or content.template_id,
        content=content,
        sections=sections,
        sources=sources,
        sha256=content_sha256(content),
        approver=approver,
        approved_at=approved_at,
    )


def load_export_data(repo, deliverable_id: str) -> ExportData:
    """Charge le livrable ; lève ExportForbidden si l'état n'est pas « approved » (garde du service)."""
    from app.generation.template_loader import TemplateError, template_for

    with repo.engine.connect() as c:
        row = c.execute(
            select(s.deliverables.c.state, s.deliverables.c.dossier_id).where(s.deliverables.c.id == deliverable_id)
        ).first()
        if row is None:
            raise KeyError(deliverable_id)
        if row.state != "approved":
            raise ExportForbidden(f"livrable à l'état « {row.state} » : seul un livrable approuvé s'exporte")
        tr = c.execute(
            select(s.state_transitions.c.user_id, s.state_transitions.c.at)
            .where(
                s.state_transitions.c.deliverable_id == deliverable_id,
                s.state_transitions.c.to_state == "approved",
            )
            .order_by(s.state_transitions.c.at.desc())
        ).first()
        doc_names = {
            d.id: d.filename
            for d in c.execute(
                select(s.documents.c.id, s.documents.c.filename).where(s.documents.c.dossier_id == row.dossier_id)
            )
        }
    version, content = repo.get_version(deliverable_id)
    from app.workflow.versions import evidence_problems

    problems = evidence_problems(repo, row.dossier_id, content)
    if problems:
        raise ExportForbidden("export refusé, preuves invalides : " + " ; ".join(problems[:5]))
    ids = [cid for sec in content.sections for sn in sec.sentences for cid in sn.source_ids]
    chunks = repo.get_chunks(row.dossier_id, list(dict.fromkeys(ids))) if ids else {}
    from app.domain.decisions import category_label
    from app.services.coeur import names

    confirmed = repo.list_decisions(row.dossier_id, status="confirmed")
    who = names(repo, [d.author_id for d in confirmed])
    decisions = {
        d.id: ExportDecision(
            text=d.text, category=category_label(d.category, content.language),
            author=who.get(d.author_id or "", labels(content.language)["unknown"]),
            date=d.confirmed_at.strftime("%Y-%m-%d") if d.confirmed_at else "—")
        for d in confirmed}
    try:
        tpl = template_for(content)
        titles, title = {x.key: x.title for x in tpl.sections}, tpl.title
    except TemplateError:
        titles, title = {}, content.template_id
    approver = tr.user_id if tr else labels(content.language)["unknown"]
    approved_at = "—"
    if tr:
        approved_at = tr.at.strftime("%Y-%m-%d") if isinstance(tr.at, datetime) else str(tr.at)[:10]
    return build_export_data(
        content, chunks, doc_names, deliverable_id=deliverable_id, version=version, approver=approver,
        approved_at=approved_at, titles=titles, title=title, decisions=decisions,
    )


def export_deliverable(repo, deliverable_id: str, fmt: str, user_id: str, out_dir: Path) -> tuple[Path, str]:
    """Produit le fichier (docx|pptx|pdf), enregistre l'export et l'audit ; renvoie (chemin, sha256 du fichier)."""
    from . import docx_export, pdf_export, pptx_export

    data = load_export_data(repo, deliverable_id)  # garde d'approbation
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{deliverable_id}-v{data.version}.{fmt}"
    if fmt == "docx":
        docx_export.render_docx(data, path)
    elif fmt == "pptx":
        pptx_export.render_pptx(data, path)
    elif fmt == "pdf":
        pdf_export.render_pdf(data, path)
    else:
        raise ValueError(f"format inconnu : {fmt}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with repo.engine.begin() as c:
        c.execute(
            insert(s.exports).values(
                id=new_id("run"), deliverable_id=deliverable_id, version=data.version, format=fmt,
                sha256=digest, path=str(path), user_id=user_id,
            )
        )
    repo.audit(
        user_id, "export", "deliverable", deliverable_id,
        {"format": fmt, "version": data.version, "content_sha256": data.sha256, "file_sha256": digest},
    )
    return path, digest
