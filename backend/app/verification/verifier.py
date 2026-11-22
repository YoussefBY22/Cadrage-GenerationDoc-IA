"""Vérificateur de sections : ancrage des phrases dans les sources (08 §4.4)."""

import re
from typing import Any

from app.domain.documents import Chunk
from app.domain.generation import SectionDraft, Sentence
from app.domain.ids import Lang
from app.domain.retrieval import Passage
from app.domain.verification import Issue, SentenceCheck, VerificationReport
from app.security import injection

from .numbers import extract_numbers
from .support import lexical_support

CANARY = "ZX-CANARI-7"


def _label(raw: str) -> str:
    return re.sub(r"[\[\]\s]", "", raw).upper()


def resolve_labels(llm: Any, passages: list[Passage], *, section_key: str = "") -> SectionDraft:
    """Traduit les étiquettes P1..Pn du modèle en identifiants de chunks.

    ``llm`` est un ``LLMSection`` (status, sentences[text, kind, sources, findings],
    missing_evidence). Étiquette inconnue : conservée telle quelle (le vérificateur la rejettera).
    """
    mapping = {p.label.upper(): p.chunk.id for p in passages}
    sentences = []
    for s in llm.sentences:
        ids: list[str] = []
        for raw in s.sources:
            cid = mapping.get(_label(raw), raw)
            if cid not in ids:
                ids.append(cid)
        sentences.append(
            Sentence(
                text=s.text,
                kind=s.kind,
                source_labels=list(s.sources),
                source_ids=ids,
                finding_ids=list(getattr(s, "findings", None) or []),
            )
        )
    return SectionDraft(
        section_key=section_key,
        status=llm.status,
        sentences=sentences,
        missing_evidence=llm.missing_evidence,
    )


def _check(
    i: int, s: Sentence, passages: dict[str, Chunk], dossier_id: str,
    known: set[str], threshold: float, lang: Lang,
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
    if s.kind == "fact" and not s.source_ids:
        add("FACT_WITHOUT_SOURCE", "fait sans source")
    for fid in s.finding_ids:
        if fid not in known:
            add("UNKNOWN_FINDING", f"constat inconnu : {fid}")
    if injection.scan(s.text) or CANARY.lower() in s.text.lower():
        add("INSTRUCTION_ECHO", "motif d'injection ou canari dans la phrase")

    mentions = extract_numbers(s.text, lang)
    found = 0
    if s.kind == "transition":
        if mentions:
            add("TRANSITION_WITH_NUMBER", "transition contenant un nombre")
    else:
        other: Lang = "en" if lang == "fr" else "fr"  # dossier mixte : source dans l'autre langue
        pool = {(n.value, n.is_percent) for c in valid
                for lg in (lang, other) for n in extract_numbers(c.text, lg)}
        for n in mentions:
            if (n.value, n.is_percent) in pool:
                found += 1
            else:
                add("NUMBER_NOT_FOUND", f"nombre absent des sources citées : {n.raw}")

    if valid:
        support = lexical_support(s.text, [c.text for c in valid], lang)
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
) -> VerificationReport:
    """Vérifie chaque phrase ; ``passages`` : chunk id -> chunk fournis au modèle."""
    checks: list[SentenceCheck] = []
    issues: list[Issue] = []
    for i, s in enumerate(draft.sentences):
        c, iss = _check(i, s, passages, dossier_id, set(known_finding_ids), support_threshold, lang)
        checks.append(c)
        issues.extend(iss)
    return VerificationReport(section_key=draft.section_key, checks=checks, issues=issues)
