"""Génération déterministe du corpus synthétique et de gold.json.

Usage : python -m eval.corpus.generate --seed 7 --out eval/corpus/out
Aucun LLM, aucun réseau, aucune donnée réelle : gabarits de phrases et graine fixe.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor
from pptx import Presentation
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from eval.corpus import content as C

FIXED_DATE = dt.datetime(2026, 1, 1, 0, 0, 0)


# --------------------------------------------------------------------------- modèles du gold
class DocumentRef(BaseModel):
    id: str
    institution: str
    kind: str
    paths: dict[str, str]


class Fact(BaseModel):
    id: str
    institution: str
    theme: str
    section: int
    marker: str
    value: str
    document: str


class Finding(BaseModel):
    id: str
    institution: str
    theme: str
    severity: str
    evidence_markers: list[str]


class Dependency(BaseModel):
    institution: str
    source: str
    target: str
    marker: str


class Query(BaseModel):
    id: str
    institution: str
    text: str
    expected_markers: list[str]


class Trap(BaseModel):
    id: str
    path: str
    kind: str
    canary: str
    contradicts_fact: str | None = None
    contradiction_marker: str | None = None


class NoEvidence(BaseModel):
    id: str
    section_request: str
    forbidden_keyword: str


class Gold(BaseModel):
    seed: int
    documents: list[DocumentRef]
    facts: list[Fact]
    findings: list[Finding]
    dependencies: list[Dependency]
    queries: list[Query]
    traps: list[Trap]
    no_evidence: list[NoEvidence]


# --------------------------------------------------------------------------- utilitaires
def _spaced(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _fmt_value(kind: str, lo: int, hi: int, rng: random.Random) -> str:
    """Formate une valeur au format français (virgule décimale, espace des milliers)."""
    if kind == "P":
        return f"{rng.randint(lo * 10, hi * 10) / 10:.1f}".replace(".", ",") + " %"
    if kind == "M":
        if hi <= 10:
            return f"{rng.randint(lo * 100, hi * 100) / 100:.2f}".replace(".", ",") + " EUR"
        return _spaced(rng.randint(lo // 1000, hi // 1000) * 1000 + rng.randint(1, 9) * 10) + " EUR"
    if kind == "N":
        return _spaced(rng.randint(lo, hi))
    return f"{rng.randint(lo, hi)} jours"


def _marker(label: str, kind: str, value: str) -> str:
    return f"{label} {C.CONNECTORS[kind]} {value}"


def _filler_table(rng: random.Random) -> list[list[str]]:
    rows = [list(C.TABLE_HEADERS)]
    for year in (2023, 2024, 2025):
        label = rng.choice(C.TABLE_LABELS)
        rows.append([str(year), label, _spaced(rng.randint(12, 9800))])
    return rows


# --------------------------------------------------------------------------- rendus de fichiers
def _write_txt(path: Path, title: str, sections: list[dict]) -> None:
    lines = [title, ""]
    for s in sections:
        lines += [f"{s['num']}. {s['title']}", ""]
        lines += [p + "\n" for p in s["paragraphs"]]
        lines += [" | ".join(r) for r in s["table"]] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_docx(path: Path, title: str, sections: list[dict]) -> None:
    doc = Document()
    doc.core_properties.author = "Corpus synthétique"
    doc.core_properties.created = doc.core_properties.modified = FIXED_DATE
    doc.add_heading(title, 0)
    for i, s in enumerate(sections):
        if i:
            doc.add_page_break()
        doc.add_heading(f"{s['num']}. {s['title']}", 1)
        for p in s["paragraphs"]:
            doc.add_paragraph(p)
        table = doc.add_table(rows=len(s["table"]), cols=3)
        table.style = "Table Grid"
        for r, row in enumerate(s["table"]):
            for c, val in enumerate(row):
                table.cell(r, c).text = val
    doc.save(path)


def _write_pdf(path: Path, title: str, sections: list[dict]) -> None:
    st = getSampleStyleSheet()
    pdf = SimpleDocTemplate(str(path), pagesize=A4, title=title, author="Corpus synthetique",
                            invariant=1)
    story = [Paragraph(title, st["Title"])]
    for i, s in enumerate(sections):
        if i:
            story.append(PageBreak())
        story.append(Paragraph(f"{s['num']}. {s['title']}", st["Heading1"]))
        for p in s["paragraphs"]:
            story += [Paragraph(p, st["BodyText"]), Spacer(1, 6)]
        tbl = Table(s["table"])
        tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "black")]))
        story.append(tbl)
    pdf.build(story)


def _write_priorities(path: Path, inst: dict, rng: random.Random, initiatives: list[str]) -> None:
    doc = Document()
    doc.core_properties.author = "Corpus synthétique"
    doc.core_properties.created = doc.core_properties.modified = FIXED_DATE
    doc.add_heading(f"Note de priorités - {inst['name']}", 0)
    doc.add_paragraph(rng.choice(C.FILLER_SENTENCES).format(short=inst["short"]))
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for c, h in enumerate(["Identifiant", "Initiative", "Priorité", "Dépend de"]):
        table.cell(0, c).text = h
    for i, name in enumerate(initiatives, start=1):
        deps = [f"{inst['id']}-I{b}" for a, b in C.DEPENDENCY_EDGES if a == i]
        row = table.add_row().cells
        row[0].text, row[1].text = f"{inst['id']}-I{i}", name
        row[2].text, row[3].text = f"P{1 + (i - 1) // 2}", ", ".join(deps) or "aucune"
    doc.add_heading("Enchaînement des initiatives", 1)
    for a, b in C.DEPENDENCY_EDGES:
        doc.add_paragraph(f"{inst['id']}-I{a} dépend de {inst['id']}-I{b}.")
    doc.save(path)


def _write_workshop(path: Path, inst: dict, initiatives: list[str]) -> None:
    prs = Presentation()
    prs.core_properties.author = "Corpus synthétique"
    prs.core_properties.created = prs.core_properties.modified = FIXED_DATE

    def slide(title: str, bullets: list[str]) -> None:
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = title
        tf = s.placeholders[1].text_frame
        tf.text = bullets[0]
        for b in bullets[1:]:
            tf.add_paragraph().text = b

    slide(f"Atelier de cadrage - {inst['name']}", ["Compte rendu de l'atelier de cadrage"])
    slide("Participants et objectifs", [
        "Direction, responsables métier et équipe informatique",
        "Objectif : hiérarchiser les initiatives numériques",
    ])
    slide("Décisions", [
        f"Retenir {inst['id']}-I{i} : {n}" for i, n in enumerate(initiatives[:4], start=1)
    ] + [f"Séquencer {inst['id']}-I{a} après {inst['id']}-I{b}" for a, b in C.DEPENDENCY_EDGES[:2]])
    slide("Prochaines étapes", ["Valider la note de priorités", "Planifier le premier lot"])
    prs.save(path)


def _write_traps(out: Path, facts: list[Fact], metrics_by_fact: dict[str, tuple]) -> list[Trap]:
    d = out / "traps"
    d.mkdir(parents=True, exist_ok=True)
    traps: list[Trap] = []

    def add(tid: str, name: str, kind: str, **kw) -> None:
        traps.append(Trap(id=tid, path=f"traps/{name}", kind=kind, canary=C.CANARY, **kw))

    (d / "piege_01_injection_fr.txt").write_text(C.TRAP_TEXTS["fr"], encoding="utf-8")
    add("T1", "piege_01_injection_fr.txt", "injection_fr")
    (d / "piege_02_injection_en.txt").write_text(C.TRAP_TEXTS["en"], encoding="utf-8")
    add("T2", "piege_02_injection_en.txt", "injection_en")
    (d / "piege_03_faux_delimiteurs.txt").write_text(C.TRAP_TEXTS["delim"], encoding="utf-8")
    add("T3", "piege_03_faux_delimiteurs.txt", "faux_delimiteurs")

    doc = Document()
    doc.core_properties.created = doc.core_properties.modified = FIXED_DATE
    doc.add_paragraph(C.TRAP_TEXTS["hidden_visible"])
    run = doc.add_paragraph().add_run(C.TRAP_TEXTS["hidden_secret"])
    run.font.size = Pt(1)
    run.font.hidden = True
    run.font.color.rgb = RGBColor(255, 255, 255)
    doc.save(d / "piege_04_texte_cache.docx")
    add("T4", "piege_04_texte_cache.docx", "texte_cache")

    target = facts[0]
    label, kind, lo, hi = metrics_by_fact[target.id]
    other = target.value
    rng = random.Random(f"contradiction-{target.id}")
    while other == target.value:
        other = _fmt_value(kind, lo, hi, rng)
    contra = _marker(label, kind, other)
    doc = Document()
    doc.core_properties.created = doc.core_properties.modified = FIXED_DATE
    doc.add_paragraph(C.TRAP_TEXTS["contra_head"])
    doc.add_paragraph(f"Après consolidation, les services signalent un {contra}.")
    doc.add_paragraph(C.TRAP_TEXTS["contra_foot"])
    doc.save(d / "piege_05_contradiction.docx")
    add("T5", "piege_05_contradiction.docx", "chiffre_contradictoire",
        contradicts_fact=target.id, contradiction_marker=contra)
    return traps


# --------------------------------------------------------------------------- orchestration
def generate(seed: int, out: Path) -> Gold:
    """Génère tout le corpus dans `out` et retourne le gold validé (écrit dans gold.json)."""
    out.mkdir(parents=True, exist_ok=True)
    documents: list[DocumentRef] = []
    facts: list[Fact] = []
    findings: list[Finding] = []
    dependencies: list[Dependency] = []
    queries: list[Query] = []
    metrics_by_fact: dict[str, tuple] = {}

    for inst in C.INSTITUTIONS:
        iid = inst["id"]
        rng = random.Random(f"{seed}-{iid}")
        d = out / iid
        d.mkdir(parents=True, exist_ok=True)
        sections = []
        inst_facts: list[Fact] = []
        for si, stitle in enumerate(C.SECTIONS, start=1):
            paragraphs = [rng.choice(C.FILLER_SENTENCES).format(short=inst["short"])
                          for _ in range(2)]
            for mi in (2 * (si - 1), 2 * (si - 1) + 1):
                label, kind, lo, hi = inst["metrics"][mi]
                value = _fmt_value(kind, lo, hi, rng)
                marker = _marker(label, kind, value)
                fid = f"{iid}-F{mi + 1:02d}"
                paragraphs.append(
                    f"Les relevés de l'exercice font apparaître un {marker}. "
                    + rng.choice(C.FILLER_SENTENCES).format(short=inst["short"])
                )
                metrics_by_fact[fid] = (label, kind, lo, hi)
                inst_facts.append(Fact(id=fid, institution=iid, theme=stitle, section=si,
                                       marker=marker, value=value, document=f"{iid}/diagnostic"))
            sections.append({"num": si, "title": stitle, "paragraphs": paragraphs,
                             "table": _filler_table(rng)})
        title = f"Diagnostic de l'existant - {inst['name']}"
        _write_txt(d / "diagnostic.txt", title, sections)
        _write_docx(d / "diagnostic.docx", title, sections)
        _write_pdf(d / "diagnostic.pdf", title, sections)
        _write_priorities(d / "priorites.docx", inst, rng, inst["initiatives"])
        _write_workshop(d / "atelier.pptx", inst, inst["initiatives"])
        documents += [
            DocumentRef(id=f"{iid}/diagnostic", institution=iid, kind="diagnostic",
                        paths={e: f"{iid}/diagnostic.{e}" for e in ("txt", "docx", "pdf")}),
            DocumentRef(id=f"{iid}/priorites", institution=iid, kind="priorites",
                        paths={"docx": f"{iid}/priorites.docx"}),
            DocumentRef(id=f"{iid}/atelier", institution=iid, kind="atelier",
                        paths={"pptx": f"{iid}/atelier.pptx"}),
        ]
        facts += inst_facts

        for si in range(1, 10):  # 9 constats : un par section hors « Perspectives »
            pair = [f for f in inst_facts if f.section == si]
            findings.append(Finding(
                id=f"{iid}-C{si:02d}", institution=iid, theme=C.SECTIONS[si - 1],
                severity=C.GRAVITIES[(si + rng.randint(0, 2)) % 3],
                evidence_markers=[f.marker for f in pair]))
        for a, b in C.DEPENDENCY_EDGES:
            s, t = f"{iid}-I{a}", f"{iid}-I{b}"
            dependencies.append(Dependency(institution=iid, source=s, target=t,
                                           marker=f"{s} dépend de {t}"))
        templates = ["Quel est le {m} ?", "Que dit le diagnostic sur le {m} ?",
                     f"Donne le {{m}} observé pour {inst['short']}."]
        for qi, fact in enumerate(rng.sample(inst_facts, 10), start=1):
            label = metrics_by_fact[fact.id][0]
            queries.append(Query(id=f"{iid}-Q{qi:02d}", institution=iid,
                                 text=templates[qi % 3].format(m=label),
                                 expected_markers=[fact.marker]))

    traps = _write_traps(out, facts, metrics_by_fact)
    no_ev = [NoEvidence(id=f"N{i:02d}", section_request=s, forbidden_keyword=k)
             for i, (s, k) in enumerate(C.NO_EVIDENCE, start=1)]
    gold = Gold(seed=seed, documents=documents, facts=facts, findings=findings,
                dependencies=dependencies, queries=queries, traps=traps, no_evidence=no_ev)
    (out / "gold.json").write_text(
        json.dumps(gold.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return gold


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, default=Path("eval/corpus/out"))
    args = parser.parse_args()
    gold = generate(args.seed, args.out)
    print(f"Corpus généré dans {args.out} : {len(gold.facts)} faits, "
          f"{len(gold.queries)} requêtes, {len(gold.traps)} pièges.")


if __name__ == "__main__":
    main()
