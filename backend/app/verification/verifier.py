"""Vérificateur de sections : ancrage des phrases dans les sources (08 §4.4)."""

import re
from typing import Any

from app.domain.documents import Chunk
from app.domain.generation import SectionDraft, Sentence
from app.domain.ids import Lang
from app.domain.retrieval import Passage
from app.domain.verification import Issue, SentenceCheck, VerificationReport
from app.security import injection

from .numbers import extract_numbers, find_ranges
from .support import lexical_support

CANARY = "ZX-CANARI-7"
# « les deux volets » peut compter une liste : avertir, pas bloquer.
SMALL_COUNT = 10


def _label(raw: str) -> str:
    return re.sub(r"[\[\]\s]", "", raw).upper()


_DEC_LABEL = re.compile(r"^D\d+$")


def resolve_labels(llm: Any, passages: list[Passage], *, section_key: str = "",
                   decisions: dict[str, str] | None = None) -> SectionDraft:
    """Traduit les étiquettes P1..Pn du modèle en identifiants de chunks.

    ``llm`` est un ``LLMSection`` (status, sentences[text, kind, sources, findings],
    missing_evidence). Étiquette inconnue : conservée telle quelle (le vérificateur la rejettera).
    """
    mapping = {p.label.upper(): p.chunk.id for p in passages}
    dmap = {k.upper(): v for k, v in (decisions or {}).items()}  # D1 -> identifiant de décision
    sentences = []
    for s in llm.sentences:
        ids: list[str] = []
        dids: list[str] = []
        # Un petit modèle met parfois « D1 » dans « sources » : on l'y reconnaît.
        for raw in s.sources:
            lab = _label(raw)
            if _DEC_LABEL.match(lab):
                dids.append(dmap.get(lab, raw))
            else:
                cid = mapping.get(lab, raw)
                if cid not in ids:
                    ids.append(cid)
        for raw in getattr(s, "decisions", None) or []:
            dids.append(dmap.get(_label(raw), raw))  # inconnue : conservée, le vérificateur rejette
        dids = list(dict.fromkeys(dids))
        sentences.append(
            Sentence(
                text=s.text,
                kind=s.kind,
                source_labels=list(s.sources),
                source_ids=ids,
                finding_ids=list(getattr(s, "findings", None) or []),
                decision_ids=dids,
            )
        )
    return SectionDraft(
        section_key=section_key,
        status=llm.status,
        sentences=sentences,
        missing_evidence=llm.missing_evidence,
    )


def _lost_ranges(mentions: list, sources: list[Chunk], lang: Lang, other: Lang) -> list[str]:
    """Nombres cités qui n'existent dans les sources que comme borne d'une fourchette tronquée."""
    cited = {n.value for n in mentions}
    alone: set = set()
    partners: dict = {}
    for c in sources:
        for lg in (lang, other):
            ranges = find_ranges(c.text, lg)
            bounds = {n.span for pair in ranges for n in pair}
            alone |= {n.value for n in extract_numbers(c.text, lg) if n.span not in bounds}
            for low, high in ranges:
                partners.setdefault(low.value, set()).add(high.value)
                partners.setdefault(high.value, set()).add(low.value)
    return [
        n.raw for n in mentions
        if n.value in partners and n.value not in alone and not (partners[n.value] & cited)
    ]


def _check(
    i: int, s: Sentence, passages: dict[str, Chunk], dossier_id: str,
    known: set[str], threshold: float, lang: Lang,
    decisions: dict[str, str] | None = None, decision_required: bool = False,
) -> tuple[SentenceCheck, list[Issue]]:
    issues: list[Issue] = []

    def add(code: str, detail: str, blocking: bool = True) -> None:
        issues.append(
            Issue(sentence_index=i, code=code, severity="blocking" if blocking else "warning", detail=detail)
        )

    valid: list[Chunk] = []
    for sid in s.source_ids:
        chunk = passages.get(sid)
        if chunk is None:
            add("UNKNOWN_SOURCE", f"source inconnue : {sid}")
        elif chunk.dossier_id != dossier_id:
            add("FOREIGN_SOURCE", f"source d'un autre dossier : {sid}")
        else:
            valid.append(chunk)
    decisions = decisions or {}
    dtexts: list[str] = []
    for did in s.decision_ids:
        if did not in decisions:  # absente, non confirmée ou d'un autre dossier
            add("UNKNOWN_SOURCE", f"décision inconnue ou non confirmée : {did}")
        else:
            dtexts.append(decisions[did])
    if s.kind == "fact" and not s.source_ids and not s.decision_ids:
        add("FACT_WITHOUT_SOURCE", "fait sans source")
    if decision_required and s.kind != "transition" and not s.decision_ids:
        add("FACT_WITHOUT_SOURCE",
            "section de décision : la phrase ne cite aucune décision humaine confirmée")
    for fid in s.finding_ids:
        if fid not in known:
            add("UNKNOWN_FINDING", f"constat inconnu : {fid}")
    if injection.scan(s.text) or CANARY.lower() in s.text.lower():
        add("INSTRUCTION_ECHO", "motif d'injection ou canari dans la phrase")

    mentions = extract_numbers(s.text, lang)
    found = 0
    if s.kind == "transition":
        if any(not n.in_words or n.is_percent or n.value > SMALL_COUNT for n in mentions):
            add("TRANSITION_WITH_NUMBER", "transition contenant un nombre")
    else:
        other: Lang = "en" if lang == "fr" else "fr"  # dossier mixte : source dans l'autre langue
        texts = [c.text for c in valid] + dtexts
        pool = {(n.value, n.is_percent) for x in texts
                for lg in (lang, other) for n in extract_numbers(x, lg)}
        for n in mentions:
            if (n.value, n.is_percent) in pool:
                found += 1
            else:
                small = n.in_words and not n.is_percent and n.value <= SMALL_COUNT
                add("NUMBER_NOT_FOUND", f"nombre absent des sources citées : {n.raw}", blocking=not small)
        for raw in _lost_ranges(mentions, valid, lang, other):
            add("RANGE_LOST", f"la source donne une fourchette, la phrase une seule borne : {raw}", False)

    if valid or dtexts:
        support = lexical_support(s.text, [c.text for c in valid] + dtexts, lang)
        if support < threshold:
            add("LOW_SUPPORT", f"appui lexical {support:.2f} < {threshold}", blocking=False)
    else:
        support = 1.0 if s.kind == "transition" else 0.0
    if any(x.severity == "blocking" for x in issues):
        status = "failed"
    else:
        status = "warning" if issues else "verified"
    check = SentenceCheck(
        index=i, status=status, numbers_cited=len(mentions), numbers_found=found, support=support
    )
    return check, issues


def verify_section(
    draft: SectionDraft,
    passages: dict[str, Chunk],
    *,
    dossier_id: str,
    known_finding_ids: set[str] = frozenset(),
    support_threshold: float = 0.3,
    lang: Lang = "fr",
    decisions: dict[str, str] | None = None,
    decision_required: bool = False,
) -> VerificationReport:
    """Vérifie chaque phrase ; ``passages`` : chunk id -> chunk fournis au modèle.

    ``decisions`` : id -> texte des décisions CONFIRMÉES du dossier (les seules citables).
    ``decision_required`` : la section exige une décision ; toute phrase doit en citer une.
    """
    checks: list[SentenceCheck] = []
    issues: list[Issue] = []
    for i, s in enumerate(draft.sentences):
        c, iss = _check(i, s, passages, dossier_id, set(known_finding_ids), support_threshold, lang,
                        decisions, decision_required)
        checks.append(c)
        issues.extend(iss)
    return VerificationReport(section_key=draft.section_key, checks=checks, issues=issues)
