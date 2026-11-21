"""Fabrique en mémoire de petits DOCX, PPTX et PDF pour les tests."""

from __future__ import annotations

import io


def make_docx(items: list[tuple[str, object]]) -> bytes:
    """items : ("h1"|"h2"|"p"|"li", texte) ou ("table", [[cellules]])."""
    from docx import Document

    doc = Document()
    for kind, value in items:
        if kind in {"h1", "h2", "h3"}:
            doc.add_heading(str(value), level=int(kind[1]))
        elif kind == "p":
            doc.add_paragraph(str(value))
        elif kind == "li":
            doc.add_paragraph(str(value), style="List Bullet")
        elif kind == "table":
            rows = value  # type: ignore[assignment]
            table = doc.add_table(rows=len(rows), cols=len(rows[0]))
            for i, row in enumerate(rows):
                for j, cell in enumerate(row):
                    table.cell(i, j).text = cell
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pptx(slides: list[tuple[str, list[str]]]) -> bytes:
    """slides : (titre, [lignes de corps])."""
    from pptx import Presentation

    prs = Presentation()
    for title, body in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = title
        slide.placeholders[1].text = "\n".join(body)
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def make_pdf(pages: list[list[str]], tiny_text: str | None = None) -> bytes:
    """pages : liste de pages, chacune une liste de lignes. tiny_text : texte en police 1 pt sur la page 1."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for index, lines in enumerate(pages):
        y = 800
        c.setFont("Helvetica", 11)
        for line in lines:
            c.drawString(60, y, line)
            y -= 22
        if tiny_text and index == 0:
            c.setFont("Helvetica", 1)
            c.drawString(60, 40, tiny_text)
        c.showPage()
    c.save()
    return buf.getvalue()
