"""Orchestration d'une génération ancrée : recherche → prompt → modèle → vérification → trace (06 §7)."""

import hashlib
import logging
import re
import secrets
import time
from collections.abc import Sequence

from sqlalchemy import select

from app.config import Settings, get_settings
from app.domain.decisions import category_label
from app.domain.generation import DeliverableContent, SectionDraft, Sentence
from app.domain.retrieval import Passage
from app.domain.verification import VerificationReport
from app.domain.workflow import CurrentUser
from app.generation.llm_schemas import LLMSection
from app.generation.prompting import (
    build_section_prompt,
    decision_cost,
    estimate_tokens,
    fit_passages,
    passage_budget,
    safe_tokens,
    system_prompt,
)
from app.generation.relevance import below_threshold, resolve_threshold
from app.generation.template_loader import (
    SectionSpec,
    Template,
    TemplateError,
    load_template,
    template_for,
)
from app.llm.base import LLMError, LLMProvider
from app.storage import schema as s
from app.verification import resolve_labels, verify_section

log = logging.getLogger("app.generation")


class GenerationError(Exception):
    """Erreur métier mappée en réponse HTTP {"error": {code, message}} par les routes."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# --- utilitaires partagés (constats, feuille de route) -------------------------------------------
def new_nonce() -> str:
    return secrets.token_hex(8)


def call_model(provider: LLMProvider, prompt: str, schema, *, lang: str = "fr",
               system: str | None = None):
    """Un appel structuré, avec UN nouvel essai si le modèle répond mal (l'erreur est rappelée).

    Renvoie (résultat | None, tentatives, latence_ms, erreur | None).
    """
    from . import jobs
    jobs.current().check()  # arrêt demandé : avant d'occuper le modèle, jamais au milieu d'une réponse
    start = time.perf_counter()
    error: str | None = None
    system = system or system_prompt(lang)
    for attempt in (1, 2):
        if error is None:
            text = prompt
        elif lang == "en":
            text = (f"{prompt}\n\nYour previous answer was invalid ({error}). "
                    "Reply only with a JSON object matching the schema.")
        else:
            text = (f"{prompt}\n\nTa réponse précédente était invalide ({error}). "
                    "Réponds uniquement par un JSON conforme au schéma.")
        try:
            result = provider.generate_structured(text, schema, system=system, temperature=0.0)
            return result, attempt, int((time.perf_counter() - start) * 1000), None
        except LLMError as exc:
            error = str(exc)[:300]
    return None, 2, int((time.perf_counter() - start) * 1000), error


def _distinct(sentences):
    """Une phrase répétée mot pour mot n'apporte rien (vu en réel : 6 fois la même) : on garde la première."""
    seen, out = set(), []
    for sn in sentences:
        key = re.sub(r"\W+", " ", sn.text.lower()).strip()
        if key not in seen:
            seen.add(key)
            out.append(sn)
    return out


SECTION_REPLY_TOKENS = 700  # place gardée pour la réponse


def record_run(repo, provider: LLMProvider, *, dossier_id: str, kind: str, prompt: str,
               status: str, attempts: int, latency_ms: int, deliverable_id: str | None = None,
               section_key: str | None = None, output: str = "") -> str:
    return repo.record_run({
        "dossier_id": dossier_id, "deliverable_id": deliverable_id, "section_key": section_key,
        "kind": kind, "provider": provider.served_model, "model": provider.served_model,
        "adapter": type(provider).__name__, "config_label": "default",
        "params": {"temperature": 0.0}, "status": status, "attempts": attempts,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "latency_ms": latency_ms,
        "tokens_in": estimate_tokens(prompt), "tokens_out": estimate_tokens(output),
    })


def get_deliverable(repo, deliverable_id: str) -> dict | None:
    """Ligne `deliverables` (la Repository n'expose pas cette lecture)."""
    with repo.engine.connect() as c:
        row = c.execute(select(s.deliverables).where(s.deliverables.c.id == deliverable_id)).first()
    return dict(row._mapping) if row else None


def find_roadmap(repo, dossier_id: str) -> str | None:
    """Identifiant de la feuille de route la plus récente du dossier."""
    with repo.engine.connect() as c:
        row = c.execute(select(s.deliverables.c.id).where(
            s.deliverables.c.dossier_id == dossier_id, s.deliverables.c.type == "roadmap"
        ).order_by(s.deliverables.c.created_at.desc(), s.deliverables.c.id.desc())).first()
    return row[0] if row else None


# --- création d'un livrable -------------------------------------------------------------------
def default_modules(repo, dossier_id: str) -> list[str]:
    """Types de projet de la fiche CONFIRMÉE : ils choisissent les modules par défaut (FR-24, FR-25)."""
    from . import context_sheet

    sheet = context_sheet.get(repo, dossier_id)
    return list(sheet.data.project_types) if sheet.confirmed else []


def create_deliverable(repo, dossier_id: str, type: str, user: CurrentUser, *,
                       initiative_id: str | None = None, language: str = "fr",
                       modules: list[str] | None = None) -> str:
    """ToR / CdC : le contexte est l'initiative choisie (conservée dans la version initiale)."""
    if type not in ("tor", "cdc"):
        raise GenerationError(422, "BAD_TYPE", "Types acceptés ici : tor, cdc "
                              "(la feuille de route se crée par roadmap:generate)")
    chosen = list(dict.fromkeys(default_modules(repo, dossier_id) if modules is None else modules))
    try:
        template = load_template(type, language, chosen)
    except TemplateError as exc:
        raise GenerationError(422, "BAD_MODULE", str(exc)) from exc
    roadmap = None
    if initiative_id is not None:
        rid = find_roadmap(repo, dossier_id)
        found = None
        if rid:
            _, rc = repo.get_version(rid)
            found = next((it for it in rc.roadmap.items if it.initiative.id == initiative_id),
                         None) if rc.roadmap else None
        if found is None:
            raise GenerationError(404, "NOT_FOUND", "Initiative introuvable dans ce dossier")
        from app.domain.roadmap import RoadmapResult
        roadmap = RoadmapResult(criteria=rc.roadmap.criteria, items=[found],
                                topo_order=[initiative_id], cycles=[], critical_path=[])
    did = repo.create_deliverable(dossier_id, type, template.id, user.id)
    repo.add_version(did, DeliverableContent(
        type=type, language=language, template_id=template.id, template_version=template.version,
        sections=[], roadmap=roadmap, modules=chosen), user.id, "generated")
    repo.audit(user.id, "deliverable.create", "deliverable", did,
               {"type": type, "initiative_id": initiative_id, "modules": chosen})
    return did


def _context(repo, deliverable: dict, content: DeliverableContent) -> tuple[dict[str, str], list[str]]:
    """Contexte injecté dans le prompt + requêtes de recherche supplémentaires."""
    ctx: dict[str, str] = {}
    extra: list[str] = []
    if content.type in ("tor", "cdc") and content.roadmap and content.roadmap.items:
        ini = content.roadmap.items[0].initiative
        ctx["initiative"] = f"{ini.title} — {ini.description}"
        extra.append(ini.title)
    if content.type in ("tor", "cdc"):  # fiche CONFIRMÉE seulement : un cadre, jamais une source
        from . import context_sheet

        fiche = context_sheet.prompt_lines(
            context_sheet.get(repo, deliverable["dossier_id"]), content.language)
        if fiche:
            ctx["fiche"] = fiche
    if content.type == "roadmap" and content.roadmap:
        titles = [it.initiative.title for it in content.roadmap.items]
        ctx["initiatives"] = " ; ".join(titles)
    return ctx, extra


def _sorted_sections(template: Template, sections: Sequence[SectionDraft]) -> list[SectionDraft]:
    order = {sp.key: i for i, sp in enumerate(template.sections)}
    return sorted(sections, key=lambda d: order.get(d.section_key, 999))


# --- génération d'une section ------------------------------------------------------------------
def generate_section(repo, provider: LLMProvider, search, deliverable_id: str, section_key: str,
                     user: CurrentUser, *, settings: Settings | None = None, proposal: bool = False) -> dict:
    """Flux 06 §7. Renvoie {version, section, report, status, attempts}."""
    settings = settings or get_settings()
    row = get_deliverable(repo, deliverable_id)
    if row is None:
        raise GenerationError(404, "NOT_FOUND", "Livrable introuvable")
    if row["state"] != "draft":
        raise GenerationError(409, "NOT_DRAFT", "Le livrable n'est plus en brouillon")
    dossier_id = row["dossier_id"]
    _, content = repo.get_version(deliverable_id)
    template = template_for(content)
    spec: SectionSpec | None = next((x for x in template.sections if x.key == section_key), None)
    if spec is None:
        raise GenerationError(404, "NOT_FOUND", "Section inconnue pour ce gabarit")

    ctx, extra = _context(repo, row, content)
    queries = list(spec.queries) + extra
    lang = content.language
    # Décisions humaines CONFIRMÉES : les seules fournies et citables (FR-23).
    confirmed = repo.list_decisions(dossier_id, status="confirmed")
    missing_cats = [c for c in spec.requires_decisions
                    if not any(d.category == c for d in confirmed)]
    decision_section = bool(spec.requires_decisions)
    passages: list[Passage] = []
    findings = repo.list_findings(dossier_id, validated_only=True) if spec.uses_findings else []
    if findings and content.roadmap and len(content.roadmap.items) == 1:
        # TdR / CdC d'UNE initiative : seulement ses constats (un vrai rapport en compte 50 à 100)
        mine = set(content.roadmap.items[0].initiative.finding_ids)
        findings = [f for f in findings if f.id in mine] or findings
    findings_not_sent = 0
    if findings:  # au plus 30 % de la fenêtre : le reste pour les passages et la réponse, jamais en silence
        window = getattr(provider, "context_tokens", None) or 4096
        room, used, kept = int(window * 0.3), 0, []
        for f in findings:
            cost = safe_tokens(f.text) + 4
            if used + cost > room:
                findings_not_sent += 1
                continue
            kept.append(f)
            used += cost
        findings = kept
    prompt, status, attempts, latency = "", "ok", 0, 0
    answer = ""
    relevance = None
    sent_decisions: list = []
    dropped_decisions = 0
    nonce = new_nonce()

    if missing_cats:  # refus SANS appel au modèle : une décision ne se devine pas
        names = ", ".join(category_label(c, lang) for c in missing_cats)
        head = "décision humaine requise" if lang == "fr" else "human decision required"
        draft = SectionDraft(section_key=section_key, status="insufficient_evidence", sentences=[],
                             missing_evidence=f"{head} : {names}")
        status = "refused"
    elif decision_section:
        # Une section qui EXIGE une décision est rendue depuis les décisions confirmées seules,
        # telles quelles et citées, SANS modèle : mesuré sur qwen3:4b, il recopie le diagnostic
        # ou attribue le texte d'une décision à un passage. Le diagnostic n'y entre jamais.
        mine = [d for d in confirmed if d.category in spec.requires_decisions]
        draft = SectionDraft(section_key=section_key, status="ok", sentences=[
            Sentence(text=d.text, kind="fact", decision_ids=[d.id]) for d in mine])
        sent_decisions = mine
    else:
        # Autres sections : décisions confirmées fournies (D1..Dn) dans 40 % de la fenêtre.
        window = getattr(provider, "context_tokens", None) or 4096
        room, used = int(window * 0.4), 0
        for d in confirmed:
            cost = decision_cost(d, nonce, lang)
            if used + cost > room:
                dropped_decisions += 1  # signalé dans la réponse et l'audit, jamais en silence
                continue
            sent_decisions.append(d)
            used += cost
        passages = search.search(dossier_id, queries, settings.retrieval_k)
        gated = False
        if len(passages) >= spec.min_sources:
            gated, relevance = below_threshold(search, dossier_id, queries,
                                               resolve_threshold(settings))
        if len(passages) < spec.min_sources:  # refus SANS appel au modèle
            draft = SectionDraft(
                section_key=section_key, status="insufficient_evidence", sentences=[],
                missing_evidence="Passages insuffisants pour les requêtes : " + " ; ".join(queries))
            status = "refused"
        elif gated and not proposal:  # porte de pertinence (le consultant peut demander une proposition) : rien d'assez proche, refus SANS appel au modèle
            draft = SectionDraft(
                section_key=section_key, status="insufficient_evidence", sentences=[],
                missing_evidence=("Aucun passage assez proche (pertinence "
                                  f"{relevance:.2f}) pour les requêtes : " + " ; ".join(queries)
                                  if relevance is not None else
                                  "Aucun passage trouvé pour les requêtes : " + " ; ".join(queries)))
            status = "refused"
        else:
            kw = {"findings": findings, "context": ctx, "nonce": nonce, "lang": lang,
                      "decisions": sent_decisions, "decision_section": False, "proposal": proposal}
            fixed = system_prompt(lang) + build_section_prompt(spec, [], **kw)
            budget = passage_budget(getattr(provider, "context_tokens", None), fixed,
                                    SECTION_REPLY_TOKENS)
            passages = fit_passages(passages, nonce, budget)  # seuls les passages lus sont citables
            prompt = build_section_prompt(spec, passages, budget=budget, **kw)
            llm, attempts, latency, error = call_model(provider, prompt, LLMSection, lang=lang)
            if llm is None:
                status = "invalid"
                draft = SectionDraft(
                    section_key=section_key, status="insufficient_evidence", sentences=[],
                    missing_evidence=f"Réponse du modèle invalide : {error}")
            else:
                answer = llm.model_dump_json()
                dmap = {f"D{i}": d.id for i, d in enumerate(sent_decisions, 1)}
                draft = resolve_labels(llm, passages, section_key=section_key, decisions=dmap)
                fmap = {f"F{i}": f.id for i, f in enumerate(findings, 1)}
                draft = draft.model_copy(update={"sentences": [
                    sn.model_copy(update={"finding_ids": [
                        fmap.get(re.sub(r"\W", "", x).upper(), x) for x in sn.finding_ids]})
                    for sn in _distinct(draft.sentences)[:spec.max_sentences]]})
                if llm.status == "insufficient_evidence":
                    status = "refused"
    report: VerificationReport = verify_section(
        draft, {p.chunk.id: p.chunk for p in passages}, dossier_id=dossier_id,
        known_finding_ids={f.id for f in findings}, support_threshold=settings.support_threshold,
        lang=content.language, decisions={d.id: d.text for d in confirmed},
        decision_required=decision_section)

    run_id = record_run(repo, provider, dossier_id=dossier_id, kind="section", prompt=prompt,
                        status=status, attempts=attempts, latency_ms=latency,
                        deliverable_id=deliverable_id, section_key=section_key, output=answer)
    repo.record_retrieval(run_id, passages)
    repo.record_verification(run_id, report)

    others = [d for d in content.sections if d.section_key != section_key]
    new_content = content.model_copy(update={"sections": _sorted_sections(template, others + [draft])})
    version = repo.add_version(deliverable_id, new_content, user.id, "generated")
    repo.audit(user.id, "section.generate", "deliverable", deliverable_id,
               {"section": section_key, "version": version, "run_id": run_id, "status": status,
                "proposal": proposal,
                "tpv": report.tpv, "relevance": relevance,
                "decisions_sent": len(sent_decisions), "decisions_not_sent": dropped_decisions, "findings_not_sent": findings_not_sent,
                "blocking": sum(i.severity == "blocking" for i in report.issues),
                "model": provider.served_model})
    return {"version": version, "run_id": run_id, "status": status, "attempts": attempts,
            "decisions_sent": len(sent_decisions), "decisions_not_sent": dropped_decisions, "findings_not_sent": findings_not_sent,
            "section": draft.model_dump(mode="json"), "report": report.model_dump(mode="json"),
            "tpv": report.tpv}
