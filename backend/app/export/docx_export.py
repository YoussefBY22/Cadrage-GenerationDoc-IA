"""Export Word : document de référence, sections, citations [n], annexe Sources, pied de page."""

from __future__ import annotations

from pathlib import Path

from docx import Document

from .common import ExportData

REFERENCE_DIR = Path(__file__).parent / "reference"


def reference_path(type_: str, lang: str = "fr") -> Path:
    return REFERENCE_DIR / f"{type_}-{lang}.docx"


def _clear_body(doc) -> None:
    body = doc.element.body
    for el in list(body):
        if not el.tag.endswith("sectPr"):
            body.remove(el)


def _table(doc, header: list[str], rows: list[list]) -> None:
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = str(v)


def _roadmap(doc, data: ExportData) -> None:
    rm = data.content.roadmap
    if rm is None:
        return
    items = sorted(rm.items, key=lambda x: x.rank)
    doc.add_heading("Initiatives priorisées", level=1)
    keys = [c.key for c in rm.criteria]
    rows = []
    for it in items:
        by = {sc.key: sc.value for sc in it.initiative.scores}
        rows.append([it.rank, it.wave, f"{it.score:.2f}", it.initiative.title, *[by.get(k, "—") for k in keys]])
    _table(doc, ["Rang", "Vague", "Score", "Initiative", *keys], rows)
    doc.add_heading("Matrice constats → initiatives", level=1)
    findings = list(dict.fromkeys(f for it in items for f in it.initiative.finding_ids))
    head = ["Constat", *[f"I{i}" for i in range(1, len(items) + 1)]]
    rows = [[f, *["●" if f in it.initiative.finding_ids else "" for it in items]] for f in findings]
    _table(doc, head, rows)
    for i, it in enumerate(items, 1):
        doc.add_paragraph(f"I{i} : {it.initiative.title}")


def render_docx(data: ExportData, path: Path) -> None:
    ref = reference_path(data.content.type, data.content.language)
    doc = Document(str(ref)) if ref.is_file() else Document()
    _clear_body(doc)
    doc.add_heading(data.title, level=0)
    for sec in data.sections:
        doc.add_heading(sec.title, level=1)
        if sec.status == "insufficient_evidence":
            doc.add_paragraph(f"Éléments insuffisants : {sec.missing_evidence or 'non précisé'}")
        for sent in sec.sentences:
            doc.add_paragraph(sent.rendered)
    _roadmap(doc, data)
    doc.add_heading("Sources", level=1)
    _table(
        doc, ["n", "Document", "Page", "Section", "Extrait"],
        [[x.n, x.document, x.page, x.section, x.excerpt] for x in data.sources],
    )
    for section in doc.sections:
        section.footer.is_linked_to_previous = False
        section.footer.paragraphs[0].text = data.footer
    doc.core_properties.title = data.title
    doc.save(str(path))
