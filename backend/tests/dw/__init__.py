"""Jeu opérationnel commun aux tests de l'entrepôt (2 dossiers, 5 runs, 3 transitions)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.domain.documents import Block, Chunk, ParsedDocument
from app.domain.generation import DeliverableContent, SectionDraft, Sentence
from app.domain.retrieval import Passage
from app.domain.verification import Issue, SentenceCheck, VerificationReport
from app.storage import schema as sc

T0 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


def _chunk(cid, doc, dos, n):
    return Chunk(id=cid, document_id=doc, dossier_id=dos, ordinal=n, text="texte", page_start=1,
                 page_end=1, section_path=(), token_estimate=3)


def _content(sections):
    return DeliverableContent(
        type="tor", language="fr", template_id="tor-fr-standard", template_version="1.0",
        sections=[SectionDraft(section_key=k, status="ok", sentences=[
            Sentence(text=t, kind="fact", source_ids=s) for t, s in sents])
            for k, sents in sections.items()])


def _check(i, status, cited, found, support):
    return SentenceCheck(index=i, status=status, numbers_cited=cited, numbers_found=found,
                         support=support)


def build_operational(repo) -> dict:
    """Construit le jeu via `SqlRepository`. Dossier A « Acme SA » (réel), B « Beta Corp » (démo)."""
    eng = repo.engine
    uid = repo.create_user("c@x.fr", "Camille Dupont", "h", "consultant")
    a = repo.create_dossier("Mission Acme", "Acme SA", "fr", uid)
    b = repo.create_dossier("Mission Beta", "Beta Corp", "fr", uid)
    with eng.begin() as c:
        c.execute(update(sc.dossiers).where(sc.dossiers.c.id == b).values(is_demo=True))
        c.execute(update(sc.dossiers).where(sc.dossiers.c.id == a).values(created_at=T0))
        c.execute(update(sc.dossiers).where(sc.dossiers.c.id == b).values(created_at=T0))
    docs = {}
    for dos, tag, mime in ((a, "A", "application/pdf"), (b, "B", "text/plain")):
        p = ParsedDocument(filename=f"{tag}.pdf", mime=mime, sha256=tag * 64, title=None,
                           language="fr", blocks=[Block(text="x", page=2)])
        doc = repo.add_document(dos, p, f"/x/{tag}")
        chunks = [_chunk(f"chk_{tag}0", doc, dos, 0), _chunk(f"chk_{tag}1", doc, dos, 1)]
        repo.add_chunks(chunks, [[1.0, 0.0], [0.0, 1.0]], "fake")
        docs[tag] = (doc, chunks)
    repo.record_alert("chk_A0", ["EXFIL_URL"])
    repo.record_alert("chk_A1", ["ROLE_OVERRIDE"])

    dlv_a = repo.create_deliverable(a, "tor", "tor-fr-standard", uid)
    dlv_b = repo.create_deliverable(b, "tor", "tor-fr-standard", uid)
    v1 = _content({
        "contexte": [("Le contexte est stable.", ["chk_A0"]),
                     ("La gouvernance est faible.", ["chk_A1", "chk_B0"])],
        "objectifs": [("Former 3 équipes.", ["chk_inconnu"])]})
    repo.add_version(dlv_a, v1, uid, "generated")
    repo.add_version(dlv_b, _content({"contexte": [("Texte beta.", ["chk_B0"])]}), uid, "generated")
    repo.set_state(dlv_a, "in_review", uid, None)            # T1, version 1
    v2 = _content({
        "contexte": [("Le contexte est stable.", ["chk_A0"]),
                     ("La gouvernance est fragile.", ["chk_A1"])],
        "objectifs": [("Former 3 équipes.", ["chk_inconnu"])]})
    repo.add_version(dlv_a, v2, uid, "edited")
    repo.set_state(dlv_a, "approved", uid, "ok")             # T2, version 2
    repo.set_state(dlv_b, "in_review", uid, None)            # T3
    # horodatage déterministe
    with eng.begin() as c:
        for dlv in (dlv_a, dlv_b):
            c.execute(update(sc.deliverables).where(sc.deliverables.c.id == dlv).values(
                created_at=T0 + timedelta(minutes=1)))
        c.execute(update(sc.deliverable_versions).values(created_at=T0 + timedelta(minutes=20)))
        rows = c.execute(sc.state_transitions.select()).all()
        order = {"in_review": 60, "approved": 180}
        for r in rows:
            minutes = 70 if r.deliverable_id == dlv_b else order[r.to_state]
            c.execute(update(sc.state_transitions).where(sc.state_transitions.c.id == r.id)
                      .values(at=T0 + timedelta(minutes=minutes)))

    def run(i, dos, kind, section, dlv, cfg, status, mins, attempts=1, lat=1000, tout=100):
        return repo.record_run({
            "id": f"run_{i}", "dossier_id": dos, "deliverable_id": dlv, "section_key": section,
            "kind": kind, "provider": "fake", "model": "m1", "config_label": cfg,
            "status": status, "attempts": attempts, "latency_ms": lat, "tokens_in": 50,
            "tokens_out": tout, "started_at": T0 + timedelta(minutes=mins)})

    run(1, a, "section", "contexte", dlv_a, "B", "ok", 10)
    run(2, a, "section", "objectifs", dlv_a, "B", "ok", 15, attempts=2, lat=3001, tout=300)
    run(3, a, "findings", None, None, "A", "refused", 20)
    run(4, b, "section", "contexte", dlv_b, "C", "ok", 16)
    run(5, b, "findings", None, None, "A", "invalid", 17)
    ch = docs["A"][1]
    repo.record_retrieval("run_1", [Passage(label="P1", chunk=ch[0], score=1.0, ranks={}),
                                    Passage(label="P2", chunk=ch[1], score=0.5, ranks={})])
    repo.record_verification("run_1", VerificationReport(
        section_key="contexte",
        checks=[_check(0, "verified", 1, 1, 0.9), _check(1, "warning", 0, 0, 0.5)],
        issues=[Issue(sentence_index=1, code="FOREIGN_SOURCE", severity="blocking", detail="x")]))
    repo.record_verification("run_2", VerificationReport(
        section_key="objectifs", checks=[_check(0, "failed", 2, 1, 0.1)],
        issues=[Issue(sentence_index=0, code="UNKNOWN_SOURCE", severity="blocking", detail="x")]))
    repo.record_verification("run_4", VerificationReport(
        section_key="contexte", checks=[_check(0, "verified", 0, 0, 0.8)], issues=[]))
    return {"uid": uid, "a": a, "b": b, "dlv_a": dlv_a, "dlv_b": dlv_b, "run": run}
