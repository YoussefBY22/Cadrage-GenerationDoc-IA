"""Orchestration d'une génération ancrée : recherche → prompt → modèle → vérification → trace (06 §7)."""

import hashlib
import logging
import re
import secrets
import time
from collections.abc import Sequence

from sqlalchemy import select

from app.config import Settings, get_settings
from app.domain.generation import DeliverableContent, SectionDraft
from app.domain.retrieval import Passage
from app.domain.verification import VerificationReport
from app.domain.workflow import CurrentUser
from app.generation.llm_schemas import LLMSection
from app.generation.prompting import build_section_prompt, estimate_tokens, system_prompt
from app.generation.template_loader import SectionSpec, Template, load_template
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


def record_run(repo, provider: LLMProvider, *, dossier_id: str, kind: str, prompt: str,
               status: str, attempts: int, latency_ms: int, deliverable_id: str | None = None,
               section_key: str | None = None, output: str = "") -> str:
    return repo.record_run({
        "dossier_id": dossier_id, "deliverable_id": deliverable_id, "section_key": section_key,
        "kind": kind, "provider": provider.name, "model": getattr(provider, "model", provider.name),
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
def create_deliverable(repo, dossier_id: str, type: str, user: CurrentUser, *,
                       initiative_id: str | None = None, language: str = "fr") -> str:
    """ToR / CdC : le contexte est l'initiative choisie (conservée dans la version initiale)."""
    if type not in ("tor", "cdc"):
        raise GenerationError(422, "BAD_TYPE", "Types acceptés ici : tor, cdc "
                              "(la feuille de route se crée par roadmap:generate)")
    template = load_template(type, language)
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
        sections=[], roadmap=roadmap), user.id, "generated")
    repo.audit(user.id, "deliverable.create", "deliverable", did,
               {"type": type, "initiative_id": initiative_id})
    return did


def _context(repo, deliverable: dict, content: DeliverableContent) -> tuple[dict[str, str], list[str]]:
    """Contexte injecté dans le prompt + requêtes de recherche supplémentaires."""
    ctx: dict[str, str] = {}
    extra: list[str] = []
    if content.type in ("tor", "cdc") and content.roadmap and content.roadmap.items:
        ini = content.roadmap.items[0].initiative
        ctx["initiative"] = f"{ini.title} — {ini.description}"
        extra.append(ini.title)
    elif content.type == "roadmap" and content.roadmap:
        titles = [it.initiative.title for it in content.roadmap.items]
        ctx["initiatives"] = " ; ".join(titles)
    return ctx, extra


def _sorted_sections(template: Template, sections: Sequence[SectionDraft]) -> list[SectionDraft]:
    order = {sp.key: i for i, sp in enumerate(template.sections)}
    return sorted(sections, key=lambda d: order.get(d.section_key, 999))


# --- génération d'une section ------------------------------------------------------------------
def generate_section(repo, provider: LLMProvider, search, deliverable_id: str, section_key: str,
                     user: CurrentUser, *, settings: Settings | None = None) -> dict:
    """Flux 06 §7. Renvoie {version, section, report, status, attempts}."""
    settings = settings or get_settings()
    row = get_deliverable(repo, deliverable_id)
    if row is None:
        raise GenerationError(404, "NOT_FOUND", "Livrable introuvable")
    if row["state"] != "draft":
        raise GenerationError(409, "NOT_DRAFT", "Le livrable n'est plus en brouillon")
    dossier_id = row["dossier_id"]
    _, content = repo.get_version(deliverable_id)
    template = load_template(content.type, content.language)
    spec: SectionSpec | None = next((x for x in template.sections if x.key == section_key), None)
    if spec is None:
        raise GenerationError(404, "NOT_FOUND", "Section inconnue pour ce gabarit")

    ctx, extra = _context(repo, row, content)
    queries = list(spec.queries) + extra
    passages: list[Passage] = search.search(dossier_id, queries, settings.retrieval_k)
    findings = repo.list_findings(dossier_id, validated_only=True) if spec.uses_findings else []
    prompt, status, attempts, latency = "", "ok", 0, 0
    answer = ""

    if len(passages) < spec.min_sources:  # refus SANS appel au modèle
        draft = SectionDraft(
            section_key=section_key, status="insufficient_evidence", sentences=[],
            missing_evidence="Passages insuffisants pour les requêtes : " + " ; ".join(queries))
        status = "refused"
    else:
        prompt = build_section_prompt(spec, passages, findings=findings, context=ctx,
                                      nonce=new_nonce(),
                                      lang=content.language)
        llm, attempts, latency, error = call_model(provider, prompt, LLMSection,
                                                   lang=content.language)
        if llm is None:
            status = "invalid"
            draft = SectionDraft(section_key=section_key, status="insufficient_evidence",
                                 sentences=[], missing_evidence=f"Réponse du modèle invalide : {error}")
        else:
            answer = llm.model_dump_json()
            draft = resolve_labels(llm, passages, section_key=section_key)
            fmap = {f"F{i}": f.id for i, f in enumerate(findings, 1)}
            draft = draft.model_copy(update={"sentences": [
                sn.model_copy(update={"finding_ids": [fmap.get(re.sub(r"\W", "", x).upper(), x)
                                                      for x in sn.finding_ids]})
                for sn in draft.sentences[:spec.max_sentences]]})
            if llm.status == "insufficient_evidence":
                status = "refused"
    report: VerificationReport = verify_section(
        draft, {p.chunk.id: p.chunk for p in passages}, dossier_id=dossier_id,
        known_finding_ids={f.id for f in findings}, support_threshold=settings.support_threshold,
        lang=content.language)

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
                "tpv": report.tpv, "blocking": sum(i.severity == "blocking" for i in report.issues),
                "model": provider.name})
    return {"version": version, "run_id": run_id, "status": status, "attempts": attempts,
            "section": draft.model_dump(mode="json"), "report": report.model_dump(mode="json"),
            "tpv": report.tpv}
