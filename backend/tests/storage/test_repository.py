"""Aller-retour de chaque méthode du dépôt, isolation entre dossiers, audit, versions."""

import inspect

import pytest
from sqlalchemy import select

from app.domain.documents import Block, Chunk, ParsedDocument
from app.domain.generation import DeliverableContent, Finding, SectionDraft, Sentence
from app.domain.retrieval import Passage
from app.domain.verification import Issue, SentenceCheck, VerificationReport
from app.storage import DuplicateDocumentError, Repository, SqlRepository
from app.storage import schema as sc
from app.storage.vector_search import cosine


def parsed(sha="a" * 64, name="a.pdf"):
    return ParsedDocument(
        filename=name, mime="application/pdf", sha256=sha, title="Titre", language="fr",
        blocks=[Block(text="x", page=1), Block(text="y", page=3)])


def mk_chunk(cid, doc, dos, n=0, text="texte"):
    return Chunk(id=cid, document_id=doc, dossier_id=dos, ordinal=n, text=text, page_start=1,
                 page_end=2, section_path=("1. A", "1.1 B"), token_estimate=5,
                 injection_flags=["EXFIL_URL"])


def content():
    return DeliverableContent(
        type="tor", language="fr", template_id="tor_fr", template_version="1",
        sections=[SectionDraft(section_key="ctx", status="ok",
                               sentences=[Sentence(text="Phrase.", kind="transition")])])


@pytest.fixture
def world(repo):
    """Deux dossiers, chacun avec un document et deux passages."""
    uid = repo.create_user("c@x.fr", "Consultant", "hash", "consultant")
    out = {"uid": uid}
    for tag, vecs in (("A", [[1.0, 0.0], [0.0, 1.0]]), ("B", [[1.0, 0.1], [0.5, 0.5]])):
        dos = repo.create_dossier(f"Dossier {tag}", "Client", "fr", uid)
        doc = repo.add_document(dos, parsed(sha=tag * 64), f"/tmp/{tag}")
        chunks = [mk_chunk(f"chk_{tag}{i}", doc, dos, i) for i in range(2)]
        repo.add_chunks(chunks, vecs, "fake")
        out[tag] = (dos, doc, chunks)
    return out


def test_users_dossiers_members(repo):
    uid = repo.create_user("a@b.fr", "A", "h", "reviewer")
    assert repo.get_user_by_email("a@b.fr")["id"] == uid
    assert repo.get_user_by_email("zz@b.fr") is None
    dos = repo.create_dossier("D", "Client", "en", uid)
    d = repo.get_dossier(dos)
    assert d["name"] == "D" and d["language"] == "en" and d["owner_id"] == uid
    assert repo.get_dossier("dos_inconnu") is None
    assert [x["id"] for x in repo.list_dossiers(uid)] == [dos]
    other = repo.create_user("o@b.fr", "O", "h", "consultant")
    assert repo.list_dossiers(other) == [] and repo.member_role(dos, other) is None
    repo.add_member(dos, other, "reviewer")
    assert repo.member_role(dos, other) == "reviewer"
    repo.add_member(dos, other, "consultant")  # mise à jour du rôle
    assert repo.member_role(dos, other) == "consultant"
    assert [x["id"] for x in repo.list_dossiers(other)] == [dos]


def test_dev_user_created(repo):
    assert repo.get_user_by_email("dev@local")["id"] == "usr_dev"


def test_documents_and_duplicates(repo, world):
    dos, doc, _ = world["A"]
    assert repo.find_document_by_sha(dos, "A" * 64) == doc
    assert repo.find_document_by_sha(dos, "z" * 64) is None
    with pytest.raises(DuplicateDocumentError):
        repo.add_document(dos, parsed(sha="A" * 64), "/tmp/dup")
    # même empreinte dans un AUTRE dossier : autorisé
    assert repo.find_document_by_sha(world["B"][0], "A" * 64) is None
    with repo.engine.connect() as c:
        assert c.execute(select(sc.documents.c.pages).where(sc.documents.c.id == doc)).scalar() == 3


def test_chunks_roundtrip_and_no_leak(repo, world):
    dos_a, doc_a, chunks_a = world["A"]
    _, doc_b, chunks_b = world["B"]
    got = repo.get_chunks(dos_a, [c.id for c in chunks_a])
    assert got["chk_A0"] == chunks_a[0] and isinstance(got["chk_A0"].section_path, tuple)
    assert repo.get_chunks(dos_a, [c.id for c in chunks_b]) == {}
    assert repo.get_chunks(dos_a, []) == {}
    assert {c.id for c in repo.iter_chunks(dos_a)} == {"chk_A0", "chk_A1"}
    assert [c.ordinal for c in repo.iter_chunks(dos_a, [doc_a])] == [0, 1]
    assert list(repo.iter_chunks(dos_a, [doc_b])) == []
    with pytest.raises(ValueError):
        repo.add_chunks(chunks_a, [[1.0]], "fake")
    repo.add_chunks([], [], "fake")


def test_vector_search_exact_order(repo):
    uid = repo.create_user("v@x.fr", "V", "h", "consultant")
    dos = repo.create_dossier("D", "C", "fr", uid)
    doc = repo.add_document(dos, parsed(), "/p")
    vecs = {"chk_1": [1.0, 0.0], "chk_2": [1.0, 1.0], "chk_3": [0.0, 1.0]}
    repo.add_chunks([mk_chunk(k, doc, dos, i) for i, k in enumerate(vecs)], list(vecs.values()),
                    "fake")
    res = repo.vector_search(dos, [1.0, 0.0], 3)
    assert [r[0] for r in res] == ["chk_1", "chk_2", "chk_3"]
    assert res[0][1] == pytest.approx(1.0) and res[1][1] == pytest.approx(2 ** -0.5)
    assert res[2][1] == pytest.approx(0.0)
    assert len(repo.vector_search(dos, [1.0, 0.0], 2)) == 2
    assert repo.vector_search(dos, [1.0, 0.0], 3, document_ids=["autre"]) == []
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_vector_search_never_leaks(repo, world):
    ids = {r[0] for r in repo.vector_search(world["A"][0], [1.0, 0.1], 50)}
    assert ids == {"chk_A0", "chk_A1"}


def test_findings(repo, world):
    dos_a = world["A"][0]
    f = Finding(id="fnd_1", dossier_id=dos_a, text="t", theme="gouvernance", severity="high",
                source_ids=["chk_A0"])
    repo.save_findings(dos_a, [f])
    repo.save_findings(dos_a, [f.model_copy(update={"validated": True, "text": "t2"})])
    assert [x.text for x in repo.list_findings(dos_a)] == ["t2"]
    assert len(repo.list_findings(dos_a, validated_only=True)) == 1
    repo.save_findings(dos_a, [Finding(id="fnd_2", dossier_id=dos_a, text="u", theme="x",
                                       severity="low", source_ids=[])])
    assert len(repo.list_findings(dos_a, validated_only=True)) == 1
    assert repo.list_findings(world["B"][0]) == []
    with pytest.raises(ValueError):
        repo.save_findings(world["B"][0], [f])


def test_versions_1_2_3_and_state(repo, world):
    dos, uid = world["A"][0], world["uid"]
    dlv = repo.create_deliverable(dos, "tor", "tor_fr", uid)
    assert [repo.add_version(dlv, content(), uid, o)
            for o in ("generated", "edited", "restored")] == [1, 2, 3]
    assert repo.get_version(dlv)[0] == 3
    v, c = repo.get_version(dlv, 2)
    assert v == 2 and c == content()
    with pytest.raises(KeyError):
        repo.get_version(dlv, 9)
    with pytest.raises(KeyError):
        repo.get_version("dlv_inconnu")
    repo.set_state(dlv, "in_review", uid, None)
    repo.set_state(dlv, "approved", uid, "ok")
    with repo.engine.connect() as c2:
        assert c2.execute(select(sc.deliverables.c.state)).scalar() == "approved"
        rows = c2.execute(select(sc.state_transitions)).all()
        assert {(r.from_state, r.to_state) for r in rows} == {("draft", "in_review"),
                                                              ("in_review", "approved")}
    with pytest.raises(KeyError):
        repo.set_state("dlv_inconnu", "approved", uid, None)


def test_traces_and_audit_append_only(repo, world):
    dos, _, chunks = world["A"]
    uid = world["uid"]
    run_id = repo.record_run(
        {"dossier_id": dos, "kind": "section", "provider": "fake", "inconnu": 1,
         "params": {"t": 0}})
    assert run_id.startswith("run_")
    passages = [Passage(label="P1", chunk=chunks[0], score=0.9, ranks={"bm25": 1, "vector": 2}),
                Passage(label="P2", chunk=chunks[1], score=0.5, ranks={"vector": 1})]
    repo.record_retrieval(run_id, passages)
    repo.record_retrieval(run_id, [])
    report = VerificationReport(
        section_key="ctx",
        checks=[SentenceCheck(index=0, status="failed", numbers_cited=1, numbers_found=0,
                              support=0.1)],
        issues=[Issue(sentence_index=0, code="NUMBER_NOT_FOUND", severity="blocking", detail="x")])
    repo.record_verification(run_id, report)
    repo.record_alert(chunks[0].id, ["EXFIL_URL"])
    with pytest.raises(KeyError):
        repo.record_alert("chk_inconnu", [])
    repo.audit(uid, "create", "dossier", dos, {"a": 1})
    repo.audit(None, "delete", "dossier", dos, {})
    with repo.engine.connect() as c:
        hits = c.execute(select(sc.retrieval_hits).order_by(sc.retrieval_hits.c.rank)).all()
        assert [(h.label, h.bm25_rank, h.vector_rank) for h in hits] == [("P1", 1, 2),
                                                                         ("P2", None, 1)]
        vr = c.execute(select(sc.verification_results)).one()
        assert vr.issues[0]["code"] == "NUMBER_NOT_FOUND"
        assert c.execute(select(sc.injection_alerts.c.dossier_id)).scalar() == dos
        log = c.execute(select(sc.audit_log).order_by(sc.audit_log.c.id)).all()
        assert [r.action for r in log] == ["create", "delete"] and log[0].details == {"a": 1}
    # ajout seul : aucune méthode ne modifie ou supprime le journal
    names = [n for n, _ in inspect.getmembers(SqlRepository, inspect.isfunction)]
    assert [n for n in names if "audit" in n] == ["audit"]


def test_foreign_keys_enforced(repo):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        repo.create_dossier("D", "C", "fr", "usr_inexistant")


def test_protocol_fully_exercised(repo, world):
    """Chaque méthode du Protocol est appelée au moins une fois (sur un enrobage espion)."""
    called: set[str] = set()

    class Spy:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            attr = getattr(self._inner, name)
            if not callable(attr):
                return attr

            def wrapper(*a, **k):
                called.add(name)
                res = attr(*a, **k)
                return list(res) if inspect.isgenerator(res) else res
            return wrapper

    spy = Spy(repo)
    uid = world["uid"]
    spy.create_user("s@x.fr", "S", "h", "admin")
    spy.get_user_by_email("s@x.fr")
    d2 = spy.create_dossier("S", "C", "fr", uid)
    spy.get_dossier(d2)
    spy.list_dossiers(uid)
    spy.add_member(d2, uid, "reviewer")
    spy.member_role(d2, uid)
    doc2 = spy.add_document(d2, parsed(sha="s" * 64), "/s")
    spy.find_document_by_sha(d2, "s" * 64)
    ch = mk_chunk("chk_s", doc2, d2)
    spy.add_chunks([ch], [[1.0, 0.0]], "fake")
    spy.get_chunks(d2, ["chk_s"])
    spy.iter_chunks(d2)
    spy.vector_search(d2, [1.0, 0.0], 1)
    spy.save_findings(d2, [Finding(id="fnd_s", dossier_id=d2, text="t", theme="t",
                                   severity="low", source_ids=[])])
    spy.list_findings(d2)
    dlv = spy.create_deliverable(d2, "cdc", "cdc_fr", uid)
    spy.add_version(dlv, content(), uid, "generated")
    spy.get_version(dlv)
    spy.set_state(dlv, "in_review", uid, None)
    run = spy.record_run({"dossier_id": d2, "kind": "section"})
    spy.record_retrieval(run, [Passage(label="P1", chunk=ch, score=1.0, ranks={})])
    spy.record_verification(run, VerificationReport(section_key="k", checks=[], issues=[]))
    spy.audit(uid, "a", "o", "1", {})
    spy.record_alert("chk_s", [])
    spy.set_document_role(doc2, "diagnostic")
    spy.document_roles(d2)
    pr = spy.create_priority(d2, title="p", description="", rank=1, status="proposed",
                             source_ids=[], author_id=uid)
    spy.get_priority(pr.id)
    spy.list_priorities(d2)
    spy.update_priority(pr.id, status="validated")
    spy.delete_priority(pr.id)
    pj = spy.create_project(d2, title="j", state="existing", duration_weeks=None, depends_on=[],
                            source_ids=[], author_id=uid)
    spy.get_project(pj.id)
    spy.list_projects(d2)
    spy.update_project(pj.id, state="done")
    spy.delete_project(pj.id)
    dc = spy.create_decision(d2, category="budget", text="40 000 euros", status="proposed",
                             author_id=uid)
    spy.get_decision(dc.id)
    spy.list_decisions(d2)
    spy.update_decision(dc.id, status="confirmed")
    spy.delete_decision(dc.id)
    from app.domain.context import ContextData

    spy.save_context(d2, ContextData(sector="Santé"), user_id=uid, confirmed=False)
    spy.get_context(d2)
    protocol_methods = {n for n, v in vars(Repository).items()
                        if callable(v) and not n.startswith("_")}
    assert protocol_methods - called == set()
