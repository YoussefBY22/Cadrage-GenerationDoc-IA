"""Génère les documents de référence Word (styles) : app/export/reference/{type}-fr.docx.

Usage : python scripts/build_reference_docx.py
"""

import datetime
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor

OUT = Path(__file__).resolve().parent.parent / "app" / "export" / "reference"
TITLES = {
    "findings": "Constats",
    "roadmap": "Feuille de route",
    "tor": "Termes de référence",
    "cdc": "Cahier des charges",
}


def build(type_: str) -> Path:
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    for name, size in (("Title", 24), ("Heading 1", 16), ("Heading 2", 13)):
        st = doc.styles[name]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    doc.core_properties.title = TITLES[type_]
    doc.core_properties.author = ""
    doc.core_properties.created = doc.core_properties.modified = datetime.datetime(2026, 1, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{type_}-fr.docx"
    doc.save(str(path))
    return path


if __name__ == "__main__":
    for t in TITLES:
        print(build(t))
