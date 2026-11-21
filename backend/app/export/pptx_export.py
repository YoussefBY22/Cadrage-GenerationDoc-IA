"""Export PowerPoint (feuille de route) : titre, synthèse, une diapositive par vague, Gantt, matrice."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Emu, Inches, Pt

from .common import ExportData

DEFAULT_WEEKS = 4
RECT, OVAL = 1, 9


def _bullets(slide, lines: list[str]) -> None:
    body = slide.placeholders[1].text_frame
    body.clear()
    for i, line in enumerate(lines or ["—"]):
        p = body.paragraphs[0] if i == 0 else body.add_paragraph()
        p.text = line
        p.font.size = Pt(16)


def gantt_schedule(items) -> list[tuple[str, int, int, int]]:
    """(titre, vague, début, fin) en semaines : les vagues se suivent, les initiatives d'une vague sont parallèles."""
    out, start = [], 0
    for wave in sorted({it.wave for it in items}):
        end = start
        for it in sorted((x for x in items if x.wave == wave), key=lambda x: x.rank):
            dur = it.initiative.duration_weeks or DEFAULT_WEEKS
            out.append((it.initiative.title, wave, start, start + dur))
            end = max(end, start + dur)
        start = end
    return out


def render_pptx(data: ExportData, path: Path) -> None:
    rm = data.content.roadmap
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.33), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.shapes.title.text = data.title
    s.placeholders[1].text = data.footer

    synth = data.sections[0] if data.sections else None
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = "Synthèse"
    _bullets(s, [x.rendered for x in synth.sentences][:6] if synth else [])

    items = sorted(rm.items, key=lambda x: x.rank) if rm else []
    for wave in sorted({it.wave for it in items}):
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = f"Vague {wave}"
        _bullets(s, [f"{it.rank}. {it.initiative.title} (score {it.score:.2f})" for it in items if it.wave == wave])

    if rm and items:
        _gantt(prs, items)
        _matrix(prs, items, [c.key for c in rm.criteria])
    prs.save(str(path))


def _gantt(prs, items) -> None:
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Calendrier (Gantt, semaines)"
    sched = gantt_schedule(items)
    total = max(e for *_, e in sched) or 1
    left, width, top, row_h = Inches(3.5), Inches(9), Inches(1.6), Inches(0.45)
    for i, (title, wave, a, b) in enumerate(sched):
        y = top + i * row_h
        label = s.shapes.add_textbox(Inches(0.4), y, Inches(3), row_h)
        label.text_frame.text = title[:40]
        label.text_frame.paragraphs[0].font.size = Pt(11)
        bar = s.shapes.add_shape(
            RECT, left + Emu(int(width * a / total)), y + Inches(0.05),
            Emu(max(int(width * (b - a) / total), 1)), row_h - Inches(0.1),
        )
        bar.text_frame.text = f"V{wave} · {b - a} sem."
        bar.text_frame.paragraphs[0].font.size = Pt(10)


def _matrix(prs, items, keys: list[str]) -> None:
    kx = "impact" if "impact" in keys else (keys[0] if keys else "")
    ky = next((k for k in ("faisabilite", "faisabilité", "feasibility") if k in keys), keys[1] if len(keys) > 1 else kx)
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = f"Matrice de priorité ({kx} × {ky})"
    x0, y0, w, h = Inches(1), Inches(1.6), Inches(11), Inches(5)
    frame = s.shapes.add_shape(RECT, x0, y0, w, h)
    frame.fill.background()
    for i, it in enumerate(items, 1):
        by = {sc.key: sc.value for sc in it.initiative.scores}
        fx, fy = (by.get(kx, 3) - 1) / 4, (by.get(ky, 3) - 1) / 4
        dot = s.shapes.add_shape(
            OVAL, x0 + Emu(int(w * fx * 0.92)), y0 + Emu(int(h * (1 - fy) * 0.9)), Inches(0.4), Inches(0.4)
        )
        dot.text_frame.text = str(i)
        dot.text_frame.paragraphs[0].font.size = Pt(10)
    legend = s.shapes.add_textbox(x0, y0 + h + Inches(0.05), w, Inches(0.5))
    legend.text_frame.text = " · ".join(f"{i}. {it.initiative.title[:30]}" for i, it in enumerate(items, 1))
    legend.text_frame.paragraphs[0].font.size = Pt(9)
