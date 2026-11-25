"""Lecture des rapports spéciaux de la Cour des comptes européenne et des réponses de la Commission.

Tout est extrait du texte tel qu'il est publié : paragraphes numérotés, blocs « Recommandation n° N » (avec
« Quand ? ») et paragraphes de réponse (« La Commission accepte / accepte partiellement / n'accepte pas »).
Aucun texte n'est écrit ici : les fonctions renvoient des morceaux exacts (lignes jointes par une espace).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_NUM_ONLY = re.compile(r"\d{1,3}")
_PARA = re.compile(r"^(\d{1,3}) (?=[A-ZÀÂÉÈÊÎÔÛÇ«])")
_REC = re.compile(r"^Recommandation n[°ºo]\s*(\d+)\s*(?:[–—-]\s*)?(.*)$")
_QUAND = re.compile(r"^(?:Quand\s?\?|Date cible[^:]*:|Délai[^:]*:)\s*(.*)$")
_ITEM = re.compile(r"^([a-z])\)\s+(.*)$")
_STANCE_START = re.compile(r"^La Commission (accepte|n[’']accepte pas|rejette|ne peut pas accepter|refuse)\b")
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[«\"A-ZÀÂÉÈÊÎÔÛÇ])")
_REF = re.compile(r"recommandation n[°ºo]\s*(\d+)\s*,?\s*(?:points?\s+)?([a-z])?\)?", re.IGNORECASE)


@dataclass
class Rec:
    number: int
    title: str
    lead: str
    items: list[tuple[str, str]]
    quand: str
    text: str = ""
    order: int = 0  # position dans le rapport


@dataclass
class Position:
    number: int
    letters: list[str]
    stance: str  # accept | partial | reject
    paragraph: str
    follow: list[str] = field(default_factory=list)


def blocks(text: str) -> list[tuple[str, bool]]:
    """Paragraphes (lignes jointes) ; le booléen dit si le bloc ressemble à un tableau ou une figure."""
    out: list[tuple[str, bool]] = []
    cur: list[str] = []
    tabular = False

    def flush() -> None:
        nonlocal cur, tabular
        if cur:
            out.append((" ".join(cur), tabular))
        cur, tabular = [], False

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
        elif _NUM_ONLY.fullmatch(line):
            continue
        else:
            tabular = tabular or bool(re.search(r"\S {3,}\S", line))
            cur.append(line)
    flush()
    return _merge_split_paragraphs(out)


def _merge_split_paragraphs(items: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    """Certains PDF laissent une ligne vide dans un paragraphe : la suite commence par une minuscule et le bloc
    précédent n'est pas fini (pas de ponctuation finale). On les recolle ; les alinéas « a) » ne sont jamais recollés."""
    out: list[tuple[str, bool]] = []
    for text, tab in items:
        if (out and re.match(r"^[a-zà-ÿ]", text) and not re.match(r"^[a-z]\)", text)
                and not re.search(r"[.:;!?»]$", out[-1][0])):
            out[-1] = (out[-1][0] + " " + text, out[-1][1] or tab)
        else:
            out.append((text, tab))
    return out


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SPLIT.split(text) if s.strip()]


def words(text: str) -> int:
    return len(text.split())


def body_paragraphs(text: str) -> list[str]:
    """Paragraphes numérotés d'un rapport, en prose (ni tableau ni figure), 25 à 180 mots."""
    out = []
    for b, tab in blocks(text):
        if tab or "...." in b or not _PARA.match(b):
            continue
        if 25 <= words(b) <= 180:
            out.append(b)
    return out


def recommendations(text: str) -> list[Rec]:
    """Recommandations du rapport (blocs complets avec lead, alinéas et « Quand ? »)."""
    bl = [b for b, _ in blocks(text)]
    found: dict[int, Rec] = {}
    for i, b in enumerate(bl):
        m = _REC.match(b)
        if not m or "...." in b:
            continue
        number, title, j = int(m.group(1)), m.group(2).strip(), i + 1
        if not title and j < len(bl):
            title, j = bl[j], j + 1
        quand, k = "", j
        while k < len(bl) and k < i + 14:
            q = _QUAND.match(bl[k])
            if q:
                quand = q.group(1).strip()
                break
            k += 1
        if not quand:
            continue
        mid = bl[j:k]
        lead_idx = next((x for x, s in enumerate(mid) if s.rstrip().endswith(":")), None)
        items = [(m2.group(1), m2.group(2)) for s in mid if (m2 := _ITEM.match(s))]
        lead = mid[lead_idx] if lead_idx is not None else ""
        if not items and not lead:  # recommandation en un seul paragraphe
            lead = " ".join(mid)
        if not lead or any(w in lead for w in ("....",)):
            continue
        rec = Rec(number=number, title=title, lead=lead.strip(), items=items, quand=quand, order=i)
        rec.text = " ".join([rec.lead] + [f"{a}) {t}" for a, t in rec.items] + [f"Quand? {quand}"])
        old = found.get(number)
        if old is None or len(rec.items) > len(old.items):
            found[number] = rec
    return sorted(found.values(), key=lambda r: r.number)


def stance_of(paragraph: str) -> str:
    first = sentences(paragraph)[0].lower() if sentences(paragraph) else ""
    if "partiellement" in first:
        return "partial"
    if re.search(r"n[’']accepte pas|rejette|ne peut pas accepter|refuse", first):
        return "reject"
    return "accept"


def positions(reply_text: str) -> dict[int, list[Position]]:
    """Réponses de la Commission, par numéro de recommandation (la table des matières est ignorée)."""
    bl = [b for b, tab in blocks(reply_text) if not tab]
    heads = [(i, int(m.group(1))) for i, b in enumerate(bl) if (m := _REC.match(b)) and "...." not in b]
    out: dict[int, list[Position]] = {}
    for idx, (i, number) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(bl)
        section = bl[i + 1:end]
        for p, b in enumerate(section):
            if not _STANCE_START.match(b):
                continue
            first = sentences(b)[0]
            if "recommandation" not in first.lower():
                continue
            ref = _REF.search(first)
            letters = re.findall(r"\b([a-z])\)", first)
            follow = []
            for nxt in section[p + 1:p + 3]:
                if _STANCE_START.match(nxt) or _REC.match(nxt):
                    break
                follow.append(nxt)
            out.setdefault(number, []).append(Position(
                number=number, letters=letters if ref else [], stance=stance_of(b), paragraph=b, follow=follow))
    return out
