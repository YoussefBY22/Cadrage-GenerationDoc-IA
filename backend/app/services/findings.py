"""Extraction des constats (« preuve d'abord ») : chaque constat est vérifié comme une phrase `fact`."""

import re

from sqlalchemy import select, update

from app.config import Settings, get_settings
from app.domain.generation import Finding, SectionDraft, Sentence
from app.domain.ids import new_id
from app.domain.retrieval import Passage
from app.domain.verification import VerificationReport
from app.domain.workflow import CurrentUser
from app.generation.llm_schemas import LLMFindings
from app.generation.prompting import (
    batch_passages,
    build_findings_prompt,
    passage_budget,
    system_prompt,
)
from app.llm.base import LLMProvider
from app.storage import schema as s
from app.verification import verify_section

from .generation import GenerationError, call_model, new_nonce, record_run

BATCH = 8  # passages par appel (06 §7)


FINDINGS_REPLY_TOKENS = 1100


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def _verify_finding(text: str, source_ids: list[str], chunks: dict, dossier_id: str,
                    settings: Settings) -> VerificationReport:
    draft = SectionDraft(section_key="findings", status="ok", sentences=[
        Sentence(text=text, kind="fact", source_ids=source_ids)])
    return verify_section(draft, chunks, dossier_id=dossier_id,
                          support_threshold=settings.support_threshold)


# Documents d'où l'on tire des constats, dans l'ordre de lecture : diagnostics d'abord (docs/15 §5).
# Une trame n'est jamais une source de faits ; stratégie et portefeuille alimentent les priorités
# et les projets (saisis par un humain), pas les constats.
READ_ORDER = ("diagnostic", "other")


EXCLUDED_WHY = {
    "strategy": "alimente les priorités, saisies par un humain",
    "portfolio": "alimente les projets existants, saisis par un humain",
    "template": "une trame n'est jamais une source de faits",
}


def _documents(repo, dossier_id: str) -> tuple[list[str], list[dict]]:
    """(documents lus dans l'ordre, documents exclus avec la raison)."""
    with repo.engine.connect() as c:
        rows = c.execute(select(s.documents.c.id, s.documents.c.role,
                                s.documents.c.filename).where(
            s.documents.c.dossier_id == dossier_id).order_by(s.documents.c.created_at,
                                                             s.documents.c.id)).all()
    read = [doc for role in READ_ORDER for doc, r, _ in rows if r == role]
    excluded = [{"document_id": d, "filename": f, "role": r,
                 "reason": EXCLUDED_WHY.get(r, "rôle non lu")} for d, r, f in rows
                if r not in READ_ORDER]
    return read, excluded


def extract(repo, provider: LLMProvider, dossier_id: str, user: CurrentUser, *,
            settings: Settings | None = None) -> dict:
    """Renvoie {findings, rejected, runs}. Un constat n'est enregistré que s'il n'a aucun
    problème bloquant ; les autres sont renvoyés dans `rejected` avec leur rapport."""
    settings = settings or get_settings()
    lang = repo.get_dossier(dossier_id)["language"]
    existing = {_norm(f.text) for f in repo.list_findings(dossier_id)}
    kept: list[Finding] = []
    reports: dict[str, dict] = {}
    rejected: list[dict] = []
    runs = 0
    docs, excluded = _documents(repo, dossier_id)
    read_chunks = failed_chunks = total_chunks = 0
    for doc_id in docs:
        chunks = list(repo.iter_chunks(dossier_id, [doc_id]))
        total_chunks += len(chunks)
        nonce = new_nonce()
        fixed = system_prompt(lang) + build_findings_prompt([], nonce=nonce, lang=lang)
        budget = passage_budget(getattr(provider, "context_tokens", None), fixed, FINDINGS_REPLY_TOKENS)
        sized = [Passage(label=f"P{BATCH}", chunk=ch, score=0.0, ranks={}) for ch in chunks]
        for group in batch_passages(sized, nonce, budget, BATCH):  # chaque passage est lu une fois
            batch = [p.chunk for p in group]
            passages = [Passage(label=f"P{n}", chunk=ch, score=0.0, ranks={})
                        for n, ch in enumerate(batch, 1)]
            prompt = build_findings_prompt(passages, nonce=nonce, budget=budget, lang=lang)
            llm, attempts, latency, _err = call_model(provider, prompt, LLMFindings, lang=lang)
            runs += 1
            run_id = record_run(repo, provider, dossier_id=dossier_id, kind="findings",
                                prompt=prompt, status="ok" if llm else "invalid",
                                attempts=attempts, latency_ms=latency,
                                output=llm.model_dump_json() if llm else "")
            repo.record_retrieval(run_id, passages)
            # Les petits modèles (qwen3:4b) renvoient parfois « insufficient_evidence » tout en listant
            # des constats sourcés : on les garde, le vérificateur ci-dessous tranche phrase par phrase.
            if llm is None:  # l'appel a échoué : ces passages n'ont PAS été lus
                failed_chunks += len(batch)
                continue
            read_chunks += len(batch)
            if llm.status != "ok" and not llm.findings:
                continue
            by_label = {p.label: p.chunk for p in passages}
            by_id = {ch.id: ch for ch in batch}
            sentences, built = [], []
            for lf in llm.findings:
                ids = [by_label[x].id for x in (re.sub(r"\W", "", t).upper() for t in lf.sources)
                       if x in by_label]
                built.append(lf)
                sentences.append(Sentence(text=lf.text, kind="fact", source_labels=list(lf.sources),
                                          source_ids=ids or list(lf.sources)))
            report = verify_section(
                SectionDraft(section_key="findings", status="ok", sentences=sentences), by_id,
                dossier_id=dossier_id, support_threshold=settings.support_threshold, lang=lang)
            repo.record_verification(run_id, report)
            for idx, lf in enumerate(built):
                blocking = [x for x in report.issues
                            if x.sentence_index == idx and x.severity == "blocking"]
                sub = report.model_copy(update={
                    "checks": [c for c in report.checks if c.index == idx],
                    "issues": [x for x in report.issues if x.sentence_index == idx]})
                if blocking:
                    rejected.append({"text": lf.text, "report": sub.model_dump(mode="json")})
                    continue
                key = _norm(lf.text)
                if key in existing:
                    continue
                existing.add(key)
                f = Finding(id=new_id("fnd"), dossier_id=dossier_id, text=lf.text, theme=lf.theme,
                            severity=lf.severity, source_ids=sentences[idx].source_ids)
                kept.append(f)
                reports[f.id] = sub.model_dump(mode="json")
    repo.save_findings(dossier_id, kept)
    repo.audit(user.id, "findings.extract", "dossier", dossier_id,
               {"saved": len(kept), "rejected": len(rejected), "runs": runs, "model": provider.name,
                "documents_read": len(docs), "chunks_read": read_chunks,
                "chunks_failed": failed_chunks, "documents_excluded": len(excluded)})
    return {"findings": [{**f.model_dump(mode="json"), "report": reports[f.id]} for f in kept],
            "rejected": rejected, "runs": runs,
            "coverage": {"documents": len(docs), "chunks_read": read_chunks,
                         "chunks_failed": failed_chunks, "chunks_total": total_chunks,
                         "excluded": excluded}}


def get_finding(repo, finding_id: str) -> Finding | None:
    with repo.engine.connect() as c:
        r = c.execute(select(s.findings).where(s.findings.c.id == finding_id)).first()
    if r is None:
        return None
    return Finding(id=r.id, dossier_id=r.dossier_id, text=r.text, theme=r.theme,
                   severity=r.severity, source_ids=list(r.source_ids), validated=bool(r.validated))


def patch_finding(repo, finding: Finding, user: CurrentUser, *, text: str | None = None,
                  validated: bool | None = None, settings: Settings | None = None) -> dict:
    """Corrige et/ou valide un constat. Le texte corrigé est re-vérifié contre ses sources ;
    un constat avec problème bloquant ne peut pas être validé."""
    settings = settings or get_settings()
    new_text = finding.text if text is None else text
    chunks = repo.get_chunks(finding.dossier_id, finding.source_ids)
    report = _verify_finding(new_text, finding.source_ids, chunks, finding.dossier_id, settings)
    blocking = any(i.severity == "blocking" for i in report.issues)
    new_valid = finding.validated if validated is None else validated
    if text is not None and validated is None:
        new_valid = False  # un texte modifié doit être revalidé
    if new_valid and blocking:
        raise GenerationError(422, "UNVERIFIED_FINDING",
                              "Constat non ancré dans ses sources : validation impossible")
    updated = finding.model_copy(update={"text": new_text, "validated": new_valid})
    repo.save_findings(finding.dossier_id, [updated])
    if validated is not None:
        with repo.engine.begin() as c:
            c.execute(update(s.findings).where(s.findings.c.id == finding.id).values(
                validated_by=user.id if new_valid else None))
    repo.audit(user.id, "finding.update", "finding", finding.id,
               {"text_changed": text is not None, "validated": new_valid})
    return {**updated.model_dump(mode="json"), "report": report.model_dump(mode="json")}
