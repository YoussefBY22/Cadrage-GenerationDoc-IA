"""Nettoyage des constats, toujours réversible et traçable.

1. **Bruit écarté par règles** : phrases de méthode (« Nous avons examiné si… »), légendes de figure,
   cellules de tableau, phrases trop courtes. Écarté ≠ supprimé : le constat reste, avec la raison.
2. **Doublons fusionnés par le sens** (vecteurs bge-m3) : le plus tardif dans le document est rattaché au
   premier (`merged_into`) ; la défusion le remet tel quel, avec ses propres preuves.
3. **Reformulation** par le modèle : « Il a été constaté que… », en mots simples, et nature du constat
   (problème, point positif, contexte). La phrase exacte du rapport est gardée dans `quote` : c'est elle la
   preuve. Garde-fou : un chiffre absent de la phrase et du passage d'origine fait rejeter la reformulation
   (on garde alors une reformulation par règle).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select, update

from ..storage import schema as s
from . import jobs
from .generation import call_model

DUP_THRESHOLD = 0.93  # 0,90 fusionnait deux constats différents sur les « orientations » (vu sur RS 17/2022)

# Un « problème » exprime un manque, un risque, un écart : sans ces marques, la phrase décrit (contexte).
NEG = re.compile(r"\b(?:ne|n['’])\s?[^.]{0,80}?\b(?:pas|plus|jamais|aucun|guère|que)\b|(?:manqu|insuffis|absen|"
                 r"lacun|risqu|faibless|incohéren|erreur|limit|fragment|défaill|retard|dépendan|concentr|conflit|"
                 r"inexact|incomplet|non\s+(?:document|systémat|fiabl)|\bsans\s|aucun|défaut|problèm|écart|"
                 r"\bseule?s?\b|réduit|\bmoins\b|bien\s+que|\bmais\b|avantage|plus\s+modestes|largement\s+recours)",
                 re.IGNORECASE)
POS = re.compile(r"(?:conforme|respect|approprié|dûment|bien\s+géré|a\s+bien\b|correctement|bons?\s+exemples?)",
                 re.IGNORECASE)


def kind_check(kind: str, quote: str) -> tuple[str, str | None]:
    """Garde-fou par règle sur la nature donnée par le modèle (il classe presque tout en « problème »)."""
    if kind == "probleme" and not NEG.search(quote):
        if POS.search(quote):
            return "positif", None
        return "contexte", ("Aucun manque ni risque exprimé dans la phrase du rapport (description ou chiffre "
                            "de cadrage) — à rétablir si c'est un constat")
    return kind, None

NOISE = [
    (re.compile(r"^\s*(?:\d{1,3}\s+)?Nous\s+(?:avons|nous\s+sommes)\s+(?:également\s+|aussi\s+)?"
                r"(?:examiné|vérifié|analysé|cherché|évalué|recueilli|interrogé|étudié|sélectionné|demandé)\b",
                re.IGNORECASE), "Méthode de l'audit (ce que les auditeurs ont fait), pas un constat"),
    (re.compile(r"^\s*(?:La|Le)\s+(?:figure|tableau|graphique|encadré)\s+\d+\s+(?:présente|montre|donne|illustre|"
                r"résume|recense|indique)(?!\s+que)", re.IGNORECASE), "Description d'une figure ou d'un tableau"),
    (re.compile(r"^\s*(?:Figure|Tableau|Encadré|Source)\s*\d*\s*[–:-]", re.IGNORECASE), "Légende ou source de figure"),
]
REWRITE_RULES = [
    (re.compile(r"^\s*(?:\d{1,3}\s+)?Nous\s+avons\s+(?:également\s+|aussi\s+)?(?:constaté|relevé|observé|noté)\s+que\s+", re.IGNORECASE),
     "Il a été constaté que "),
    (re.compile(r"^\s*(?:\d{1,3}\s+)?Nous\s+avons\s+(?:également\s+|aussi\s+)?(?:constaté|relevé|observé)\s+", re.IGNORECASE),
     "Il a été constaté "),
    (re.compile(r"^\s*(?:\d{1,3}\s+)?Nous\s+n['’]avons\s+pas\s+trouvé\s+", re.IGNORECASE), "Il n'a pas été trouvé "),
]


class LLMRewrite(BaseModel):
    nature: Literal["probleme", "positif", "contexte"]
    texte: str = Field(max_length=500)


def noise_reason(text: str) -> str | None:
    t = text.strip()
    if len(t) < 45 and not re.search(r"\b(?:ne|n['’]|pas|aucun|insuffis|manque|risque)\b", t, re.IGNORECASE):
        return "Phrase trop courte ou isolée (souvent une cellule de tableau), pas un constat complet"
    for rx, why in NOISE:
        if rx.search(t):
            return why
    return None


def rule_rewrite(text: str) -> str:
    t = " ".join(text.split())
    for rx, repl in REWRITE_RULES:
        if rx.search(t):
            return rx.sub(repl, t, count=1)
    t = re.sub(r"^\d{1,3}\s+(?=[A-ZÀ-Ý])", "", t)  # numéro de paragraphe collé
    t = re.sub(r"^(?:Cela étant|Par conséquent|En outre|Toutefois|Cependant|Néanmoins|De plus|Ainsi|"
               r"D['’]une manière générale|En revanche|Enfin|Par ailleurs)\s*,\s*", "", t, flags=re.IGNORECASE)
    t = t[:1].upper() + t[1:]
    return "Il a été constaté que " + t[0].lower() + t[1:] if t and t[0].isupper() and not t.startswith("Il a été") else t


def _numbers(t: str) -> set[str]:
    return {n.replace(" ", "").replace(" ", "") for n in re.findall(r"\d[\d  ]*(?:[.,]\d+)?", t)}


def _prompt(quote: str, context: str) -> str:
    return (
        "Tu aides un consultant à relire les constats d'un rapport d'audit.\n"
        f"PHRASE DU RAPPORT : « {quote} »\n"
        f"PASSAGE AUTOUR (pour comprendre les mots comme « cela », « ces risques », « elle ») : « {context} »\n\n"
        "1. nature :\n"
        "- \"probleme\" : un manque, une faiblesse, un risque ou un écart constaté ;\n"
        "- \"positif\" : quelque chose qui fonctionne correctement ;\n"
        "- \"contexte\" : une description, un chiffre de cadrage, la méthode de l'audit, une légende ou une "
        "cellule de tableau ; ce n'est pas un constat.\n"
        "2. texte : réécris la phrase pour un lecteur non spécialiste. Commence par « Il a été constaté que ». "
        "Une ou deux phrases courtes, sujet explicite (remplace « cela », « ces », « elle » par ce qu'ils "
        "désignent d'après le passage). Simplifie la phrase, PAS le vocabulaire métier : garde les termes précis "
        "du rapport (« rendre compte », « dépendance excessive », « évaluation des besoins »…). Ne change pas le "
        "sens : une condition (« si… ») ou une règle (« sont censées ») n'est pas un manque constaté. N'ajoute "
        "AUCUN fait, chiffre ou nom absent de la phrase ou du passage.\n"
        'Réponds uniquement en JSON : {"nature": "...", "texte": "..."}'
    )


def _rows(c, dossier_id):
    f = s.findings.c
    return c.execute(select(f.id, f.text, f.quote, f.kind, f.status, f.merged_into, f.source_ids, f.validated)
                     .where(f.dossier_id == dossier_id)).all()


def clean(repo, provider, dossier_id: str, *, rewrite: bool = True, embed_provider=None) -> dict:
    """Nettoie les constats pas encore traités (`kind` vide). Idempotent ; réversible ligne par ligne."""
    job = jobs.current()
    eng = repo.engine
    with eng.connect() as c:
        rows = [r for r in _rows(c, dossier_id) if r.kind is None]
        chunk_text = {r.id: r.text for r in c.execute(select(s.chunks.c.id, s.chunks.c.text)
                                                       .where(s.chunks.c.dossier_id == dossier_id))}
        order = {r.id: (r.document_id, r.ordinal) for r in c.execute(
            select(s.chunks.c.id, s.chunks.c.document_id, s.chunks.c.ordinal).where(s.chunks.c.dossier_id == dossier_id))}
    stats = {"discarded": 0, "merged": 0, "rewritten": 0, "rule_rewritten": 0, "processed": len(rows)}
    if not rows:
        job.step("Aucun nouveau constat à nettoyer")
        return stats
    job.step(f"Nettoyage de {len(rows)} constat(s) : bruit, doublons, reformulation")

    # 1. bruit
    noisy = {}
    for r in rows:
        why = noise_reason(r.quote or r.text)
        if why:
            noisy[r.id] = why
    with eng.begin() as c:
        for fid, why in noisy.items():
            c.execute(update(s.findings).where(s.findings.c.id == fid).values(
                status="discarded", discard_reason=why, kind="contexte",
                quote=next(r.quote or r.text for r in rows if r.id == fid)))
    stats["discarded"] += len(noisy)
    job.step(f"{len(noisy)} phrase(s) écartée(s) par règle (méthode, figure, cellule de tableau)")

    # 2. doublons par le sens, contre tous les constats actifs du dossier (anciens compris)
    with eng.connect() as c:
        active = [r for r in _rows(c, dossier_id) if r.status != "discarded" and r.merged_into is None]
    def pos(r):
        return min((order.get(x, ("", 10**6)) for x in (r.source_ids or [])), default=("", 10**6))
    active.sort(key=pos)
    todo = {r.id for r in rows} - set(noisy)
    emb = embed_provider or provider
    try:
        vecs = emb.embed([(r.quote or r.text) for r in active]) if len(active) > 1 else []
    except Exception:  # noqa: BLE001 — sans vecteurs, pas de fusion ; signalé
        vecs = []
        job.step("Vecteurs indisponibles : doublons non recherchés")
    merged = {}
    for i, r in enumerate(active):
        if r.id not in todo or not vecs:
            continue
        for j in range(i):
            o = active[j]
            if o.id in merged:
                continue
            sim = sum(a * b for a, b in zip(vecs[i], vecs[j], strict=False))
            if sim >= DUP_THRESHOLD:
                merged[r.id] = o.id
                break
    with eng.begin() as c:
        for fid, target in merged.items():
            c.execute(update(s.findings).where(s.findings.c.id == fid).values(merged_into=target))
    stats["merged"] = len(merged)
    job.step(f"{len(merged)} doublon(s) fusionné(s) dans un constat existant (défusion possible)")

    # 3. reformulation
    left = [r for r in rows if r.id not in noisy and r.id not in merged]
    job.phase(len(left), "constats reformulés")
    for n, r in enumerate(left, 1):
        quote = r.quote or r.text
        context = " ".join(chunk_text.get(x, "") for x in (r.source_ids or [])[:1])
        k = context.find(quote[:40])
        context = context[max(0, k - 400): k + len(quote) + 200] if k >= 0 else context[:700]
        kind, text, by_model = "probleme", rule_rewrite(quote), False
        if rewrite:
            job.step(f"Reformulation {n}/{len(left)} : « {quote[:70]}… »")
            llm, *_ = call_model(provider, _prompt(quote, context), LLMRewrite)
            if llm and llm.texte.strip():
                new = " ".join(llm.texte.split())
                if _numbers(new) <= _numbers(quote) | _numbers(context) and len(new) <= 500:
                    kind, text, by_model = llm.nature, new, True
                else:
                    kind = llm.nature
                    job.step(f"Reformulation {n} refusée (chiffre absent de la source) : règle simple à la place")
        kind, why = kind_check(kind, quote)
        values = {"quote": quote, "text": text, "kind": kind, "rewritten": True}
        if kind == "contexte":
            values.update(status="discarded",
                          discard_reason=why or "Contexte ou description, pas un constat (jugé par l'IA)")
            stats["discarded"] += 1
        with eng.begin() as c:
            c.execute(update(s.findings).where(s.findings.c.id == r.id).values(**values))
        stats["rewritten" if by_model else "rule_rewritten"] += 1
        job.advance()
    return stats


def unmerge(repo, finding_id: str) -> None:
    with repo.engine.begin() as c:
        c.execute(update(s.findings).where(s.findings.c.id == finding_id).values(merged_into=None))


def merge(repo, finding_id: str, target_id: str) -> None:
    with repo.engine.begin() as c:
        c.execute(update(s.findings).where(s.findings.c.id == finding_id).values(merged_into=target_id))
        # ce qui était fusionné dans le constat absorbé suit sa nouvelle cible
        c.execute(update(s.findings).where(s.findings.c.merged_into == finding_id).values(merged_into=target_id))


def restore(repo, finding_id: str) -> None:
    """Remet un constat écarté dans la liste active."""
    with repo.engine.begin() as c:
        c.execute(update(s.findings).where(s.findings.c.id == finding_id).values(
            status=None, discard_reason=None, kind="probleme"))


def discard(repo, finding_id: str, reason: str) -> None:
    with repo.engine.begin() as c:
        c.execute(update(s.findings).where(s.findings.c.id == finding_id).values(
            status="discarded", discard_reason=reason[:200] or "Écarté par le consultant", validated=False))


def use_original(repo, finding_id: str) -> None:
    """Annule la reformulation : le texte redevient la phrase exacte du rapport."""
    with repo.engine.begin() as c:
        row = c.execute(select(s.findings.c.quote).where(s.findings.c.id == finding_id)).first()
        if row and row.quote:
            c.execute(update(s.findings).where(s.findings.c.id == finding_id).values(text=row.quote, rewritten=False))
