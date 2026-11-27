"""Contenu complet d'une recommandation, repris du rapport par règles (aucun modèle) :
phrase d'introduction, sous-points a), b), c)…, échéance (« Quand ? D'ici à décembre 2023 ») et
paragraphes du rapport cités à l'appui dans la conclusion qui la précède (« (points 18 à 26) »).

Le texte du document est reconstitué à partir de ses passages, dans l'ordre ; chaque position renvoie à
son passage et à sa page. Tout ce qui est repris est une copie exacte du rapport.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TITLE = re.compile(
    r"\bRecomm(?:a|e)ndation\s+(?:n\s*[°o]\s*|no\.?\s*|#\s*)?(\d{1,2})\s*[–—:\-]\s*", re.IGNORECASE)
DEADLINE = re.compile(
    r"(?:Quand\s*\?|[ÉE]ch[ée]ance\s*:|D[ée]lai\s*:|Calendrier\s*:|Date\s+(?:cible|de\s+mise\s+en\s+[œo]e?uvre)\s*:"
    r"|When\s*\?|Timeframe\s*:|Target\s+(?:implementation\s+)?date\s*:)\s*(.{3,160}?)(?:\.(?=\s|$)|\n\n|$)",
    re.IGNORECASE | re.DOTALL)
SUB = re.compile(r"(?:(?<=\s)|^)([a-h])\)\s+")
POINTS = re.compile(r"\((?:voir\s+)?(?:les\s+)?(?:points?|paragraphes?|paragraphs?|§)\s+([^)]{1,80})\)", re.IGNORECASE)
CONCLUSIONS = re.compile(r"\bConclusions?\s+(?:et|and)\s+recomm[ae]ndations?\b", re.IGNORECASE)
# fin du titre : début de la phrase d'introduction
INTRO_START = re.compile(r"(?<=\S)\s+(?=(?:La|Le|Les|L'|L’|Nous|Il|Elle|Ce|Cette|The|We|It)\s)")


@dataclass
class Span:
    start: int
    end: int
    chunk_id: str
    page_start: int | None
    page_end: int | None


def assemble(chunks: list[tuple[str, int | None, int | None, str]]) -> tuple[str, list[Span]]:
    """[(chunk_id, page_start, page_end, texte)] dans l'ordre → texte complet et correspondance."""
    parts, spans, pos = [], [], 0
    for cid, p1, p2, text in chunks:
        spans.append(Span(pos, pos + len(text), cid, p1, p2))
        parts.append(text)
        pos += len(text) + 2
    return "\n\n".join(parts), spans


def where(spans: list[Span], pos: int) -> Span | None:
    for sp in spans:
        if sp.start <= pos <= sp.end:
            return sp
    return spans[-1] if spans else None


def numbers(expr: str) -> list[int]:
    """« 18 à 26 » → 18…26 ; « 24 et 28 à 32 » → 24, 28…32 ; « 57 à 71 » ; « 4, 7 and 9-11 »."""
    out: list[int] = []
    for a, b in re.findall(r"(\d{1,3})(?:\s*(?:à|to|-|–)\s*(\d{1,3}))?", expr):
        lo, hi = int(a), int(b) if b else int(a)
        if hi < lo or hi - lo > 80:
            hi = lo
        out += range(lo, hi + 1)
    return sorted(set(out))


def _clean(t: str) -> str:
    t = " ".join(t.split())
    t = re.sub(r"(?<=[;:.,])\s+\d{1,3}$", "", t)  # numéro de page collé en fin de bloc (« …interne; 43 »)
    return t.strip(" ;,")


def parse(full: str, spans: list[Span]) -> dict[int, dict]:
    """n° → {title, intro, sub_points, deadline, points, quote, page, chunk_id}. Prend, pour chaque numéro,
    l'occurrence suivie d'un vrai contenu (pas une mention dans le sommaire ou la synthèse)."""
    hits = [(m.start(), m.end(), int(m.group(1))) for m in TITLE.finditer(full)]
    found: dict[int, dict] = {}
    concs = [m.start() for m in CONCLUSIONS.finditer(full)]
    for i, (start, body_start, n) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(full)
        block = full[body_start:end]
        dl = DEADLINE.search(block)
        if dl:
            block = block[: dl.end()]
        # titre : jusqu'au début de la phrase d'introduction (ou 200 caractères)
        flat = " ".join(block.split())
        m_intro = INTRO_START.search(flat, 15)
        title = flat[: m_intro.start()] if m_intro else flat[:200]
        rest = flat[m_intro.start():].strip() if m_intro else ""
        if dl:
            rest = rest[: rest.lower().rfind(dl.group(0).split()[0].lower())].strip() if rest else rest
        subs = []
        marks = list(SUB.finditer(rest))
        intro = rest[: marks[0].start()].strip() if marks else rest
        for j, mk in enumerate(marks):
            stop = marks[j + 1].start() if j + 1 < len(marks) else len(rest)
            subs.append({"label": mk.group(1), "text": _clean(rest[mk.end():stop])})
        # paragraphes cités : dans le texte entre la recommandation précédente (ou le titre « Conclusions ») et celle-ci
        heading = max((c for c in concs if c < start), default=max(0, start - 3000))
        prev_end = hits[i - 1][1] if i else heading
        before = full[max(prev_end, start - 4000):start]
        pts = sorted({x for m in POINTS.finditer(before) for x in numbers(m.group(1))})
        content = len(intro) > 20 or subs or dl
        sp = where(spans, start)
        item = {"number": n, "title": _clean(title)[:300], "intro": _clean(intro)[:2000] or None,
                "sub_points": subs or None, "deadline": _clean(dl.group(1))[:200] if dl else None,
                "points": pts or None, "quote": _clean(full[start:body_start] + block)[:6000],
                "page": sp.page_start if sp else None, "chunk_id": sp.chunk_id if sp else None,
                "_content": bool(content)}
        if n not in found or (item["_content"] and not found[n]["_content"]):
            found[n] = item
    for v in found.values():
        v.pop("_content")
    return found


PARA = re.compile(r"(?:^|\n|(?<=[.;:)»]) )[ \t]*(\d{1,3})[ \t]+(?=[A-ZÀ-ÝÉÈ«\"“(])")  # début de ligne ou après une fin de phrase ; un numéro de page seul (ligne isolée) ne compte pas


def paragraph_at(full: str, pos: int) -> int | None:
    """Numéro du paragraphe du rapport qui contient la position `pos` (rapports à paragraphes numérotés)."""
    last = None
    for m in PARA.finditer(full, 0, pos + 1):
        n = int(m.group(1))
        if last is None or 0 < n - last <= 5:  # suite plausible : écarte les numéros de page et d'année
            last = n
    return last


class Locator:
    """Retrouve une phrase dans le texte complet malgré les retours à la ligne et espaces multiples."""

    def __init__(self, full: str):
        self.full = full
        out, idx, space = [], [], False
        for i, ch in enumerate(full):
            if ch.isspace():
                if not space:
                    out.append(" ")
                    idx.append(i)
                space = True
            else:
                out.append(ch.lower())
                idx.append(i)
                space = False
        self.norm = "".join(out)
        self.idx = idx

    def find(self, sentence: str) -> int | None:
        key = " ".join(sentence.lower().split())
        for probe in (key, key[:80], key[-80:]):
            if len(probe) < 15:
                continue
            k = self.norm.find(probe)
            if k >= 0:
                return self.idx[k]
        return None


def finding_links(full: str, sentences: dict[str, str], recs: list[dict]) -> dict[str, dict]:
    """constat → {paragraph, recommendation_ids} : le paragraphe du rapport où se trouve sa phrase, et les
    recommandations dont la conclusion cite ce paragraphe (« (points 18 à 26) »)."""
    loc = Locator(full)
    out = {}
    for fid, sentence in sentences.items():
        pos = loc.find(sentence)
        para = paragraph_at(full, pos) if pos is not None else None
        ids = [r["id"] for r in recs if para is not None and para in (r.get("points") or [])]
        out[fid] = {"paragraph": para, "recommendation_ids": ids, "found": pos is not None}
    return out


def dossier_links(repo, dossier_id: str) -> tuple[dict, dict]:
    """(liens constat → {paragraph, recommendation_ids, found}, lignes constats {id: row}) pour tout le dossier."""
    from sqlalchemy import select

    from ..storage import schema as s
    f, ch, rc = s.findings.c, s.chunks.c, s.audit_recommendations.c
    with repo.engine.connect() as c:
        rows = {r.id: r for r in c.execute(select(f.id, f.text, f.quote, f.kind, f.status, f.discard_reason,
                                                  f.merged_into, f.rewritten, f.source_ids)
                                           .where(f.dossier_id == dossier_id))}
        chunks = c.execute(select(ch.id, ch.document_id, ch.page_start, ch.page_end, ch.text)
                           .where(ch.dossier_id == dossier_id).order_by(ch.document_id, ch.ordinal)).all()
        recs = [dict(r._mapping) for r in c.execute(select(rc.id, rc.document_id, rc.number, rc.points, rc.status)
                                                     .where(rc.dossier_id == dossier_id))]
    doc_of = {x.id: x.document_id for x in chunks}
    links: dict = {}
    for doc in {x.document_id for x in chunks}:
        full, _ = assemble([(x.id, x.page_start, x.page_end, x.text) for x in chunks if x.document_id == doc])
        mine = {r.id: (r.quote or r.text) for r in rows.values()
                if any(doc_of.get(i) == doc for i in (r.source_ids or []))}
        drecs = [r for r in recs if r["document_id"] == doc and r["status"] in ("proposed", "validated")]
        links.update(finding_links(full, mine, drecs))
    return links, rows
