"""Orchestration de la génération (services) avec FakeProvider : honnête, tricheur, essai, refus."""

import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.domain.workflow import CurrentUser
from app.llm import FakeProvider
from app.llm.base import LLMError
from app.services import findings, generation, ingestion, roadmap_service
from app.services.generation import GenerationError
from app.services.search import SearchService
from app.storage import schema as s

from .test_generation_fakes import FlakyOnce, cheater, honest

USER = CurrentUser(id="usr_dev", role="admin")
DOCS = [
    ("Contexte institutionnel et enjeux\n\nLa direction informatique gère quarante applications "
        "métiers dispersées dans six services du ministère.\n"),
    ("Constats du diagnostic\n\nLe comité de pilotage numérique se réunit chaque trimestre pour "
        "arbitrer les priorités du diagnostic.\n\nLe budget informatique annuel représente 3,2 millions "
        "d'euros pour 120 agents.\n"),
    ("Enjeux de gouvernance\n\nLes données clients sont stockées dans trois bases sans référentiel "
        "commun, ce qui nuit aux enjeux institutionnels.\n"),
]


def _setup(repo, provider, tmp_path, *, with_doc=True):
    settings = Settings(upload_dir=str(tmp_path / "up"))
    search = SearchService(repo, provider)
    did = repo.create_dossier("D", "Client", "fr", "usr_dev")
    repo.add_member(did, "usr_dev", "consultant")
    if with_doc:  # trois petits documents = trois passages (min_sources des gabarits = 2)
        for i, body in enumerate(DOCS):
            ingestion.ingest(repo, provider, did, f"note{i}.txt", body.encode(), USER,
                             search=search, settings=settings)
    return did, search, settings


def _count(repo, table, **where):
    with repo.engine.connect() as c:
        q = select(func.count()).select_from(table)
        for k, v in where.items():
            q = q.where(table.c[k] == v)
        return c.execute(q).scalar()


def _tor(repo, did):
    return generation.create_deliverable(repo, did, "tor", USER)


def test_honnete_tpv_1(repo, tmp_path):
    p = FakeProvider(handler=honest)
    did, search, st = _setup(repo, p, tmp_path)
    dl = _tor(repo, did)
    r = generation.generate_section(repo, p, search, dl, "contexte", USER, settings=st)
    assert r["status"] == "ok" and r["tpv"] == 1.0 and r["attempts"] == 1
    assert not [i for i in r["report"]["issues"] if i["severity"] == "blocking"]
    _, content = repo.get_version(dl)
    assert [d.section_key for d in content.sections] == ["contexte"]
    assert _count(repo, s.generation_runs, deliverable_id=dl) == 1
    assert _count(repo, s.retrieval_hits, run_id=r["run_id"]) > 0
    assert _count(repo, s.verification_results, run_id=r["run_id"]) == 2


def test_tricheur_problemes_bloquants_enregistres(repo, tmp_path):
    p = FakeProvider(handler=cheater)
    did, search, st = _setup(repo, p, tmp_path)
    dl = _tor(repo, did)
    r = generation.generate_section(repo, p, search, dl, "contexte", USER, settings=st)
    codes = {i["code"] for i in r["report"]["issues"] if i["severity"] == "blocking"}
    assert {"UNKNOWN_SOURCE", "NUMBER_NOT_FOUND", "FACT_WITHOUT_SOURCE"} <= codes
    assert r["tpv"] == 0.0
    with repo.engine.connect() as c:
        rows = c.execute(select(s.verification_results).where(
            s.verification_results.c.run_id == r["run_id"])).fetchall()
    assert rows and all(row.status == "failed" and row.issues for row in rows)
    _, content = repo.get_version(dl)  # la phrase fautive est conservée (marquée), pas supprimée
    assert len(content.sections[0].sentences) == 2


def test_json_invalide_puis_valide(repo, tmp_path):
    p = FakeProvider(handler=FlakyOnce())
    did, search, st = _setup(repo, p, tmp_path)
    dl = _tor(repo, did)
    r = generation.generate_section(repo, p, search, dl, "contexte", USER, settings=st)
    assert r["attempts"] == 2 and r["status"] == "ok"
    assert "invalide" in p.calls[1]["prompt"]
    with repo.engine.connect() as c:
        assert c.execute(select(s.generation_runs.c.attempts).where(
            s.generation_runs.c.id == r["run_id"])).scalar() == 2


def test_deux_echecs_statut_invalid(repo, tmp_path):
    def bad(prompt, schema):
        raise LLMError("non")

    p = FakeProvider(handler=bad)
    did, search, st = _setup(repo, p, tmp_path)
    dl = _tor(repo, did)
    r = generation.generate_section(repo, p, search, dl, "contexte", USER, settings=st)
    assert r["status"] == "invalid" and r["section"]["status"] == "insufficient_evidence"
    assert len(p.calls) == 2


def test_refus_sans_preuve_aucun_appel(repo, tmp_path):
    p = FakeProvider(handler=honest)
    did, search, st = _setup(repo, p, tmp_path, with_doc=False)
    dl = _tor(repo, did)
    r = generation.generate_section(repo, p, search, dl, "contexte", USER, settings=st)
    assert p.calls == [] and r["status"] == "refused" and r["tpv"] == 1.0
    assert r["report"]["issues"] == []
    assert r["section"]["missing_evidence"]
    assert _count(repo, s.generation_runs, status="refused") == 1


def test_section_inconnue_et_etat(repo, tmp_path):
    p = FakeProvider(handler=honest)
    did, search, st = _setup(repo, p, tmp_path)
    dl = _tor(repo, did)
    with pytest.raises(GenerationError) as e:
        generation.generate_section(repo, p, search, dl, "nope", USER, settings=st)
    assert e.value.status == 404
    repo.set_state(dl, "in_review", "usr_dev", None)
    with pytest.raises(GenerationError) as e:
        generation.generate_section(repo, p, search, dl, "contexte", USER, settings=st)
    assert e.value.status == 409


def test_constats_puis_feuille_de_route(repo, tmp_path):
    p = FakeProvider(handler=honest)
    did, _search, st = _setup(repo, p, tmp_path)
    with pytest.raises(GenerationError) as e:  # pas de constat validé
        roadmap_service.generate(repo, p, did, USER)
    assert e.value.status == 409
    out = findings.extract(repo, p, did, USER, settings=st)
    assert out["findings"] and not out["rejected"]
    assert all(f["report"]["issues"] == [] for f in out["findings"])
    for f in repo.list_findings(did):
        findings.patch_finding(repo, f, USER, validated=True)
    r = roadmap_service.generate(repo, p, did, USER)
    road = r["roadmap"]
    assert [it["initiative"]["title"] for it in road["items"]] == ["Initiative A", "Initiative B"]
    a, b = (it["initiative"] for it in road["items"])
    assert b["depends_on"] == [a["id"]] and road["cycles"] == []
    # recalcul sans modèle : B devient la plus prioritaire, avec durées
    n = len(p.calls)
    out = roadmap_service.patch(repo, r["deliverable_id"], USER, [
        {"id": b["id"], "scores": [{"key": "impact", "value": 5}, {"key": "urgence", "value": 5}],
         "duration_weeks": 4}, {"id": a["id"], "duration_weeks": 6}])
    assert len(p.calls) == n
    assert out["version"] == 2 and out["roadmap"]["critical_path"] == [a["id"], b["id"]]
    # un cycle est signalé, pas une erreur
    out = roadmap_service.patch(repo, r["deliverable_id"], USER,
                                [{"id": a["id"], "depends_on": [b["id"]]}])
    assert out["roadmap"]["cycles"] and out["roadmap"]["critical_path"] == []
    with pytest.raises(GenerationError):
        roadmap_service.patch(repo, r["deliverable_id"], USER,
                              [{"id": a["id"], "depends_on": ["x"]}])


def test_constats_gardes_malgre_statut_incoherent(repo, tmp_path):
    """qwen3:4b renvoie parfois status=insufficient_evidence AVEC des constats sourcés (constaté en réel)."""
    def incoherent(prompt, schema):
        out = honest(prompt, schema)
        if isinstance(out, dict) and "findings" in out:
            out = {**out, "status": "insufficient_evidence"}
        return out

    p = FakeProvider(handler=incoherent)
    did, _search, st = _setup(repo, p, tmp_path)
    out = findings.extract(repo, p, did, USER, settings=st)
    assert out["findings"] and not out["rejected"]


def test_refus_sans_constat_ignore(repo, tmp_path):
    p = FakeProvider(handler=lambda prompt, schema: {"status": "insufficient_evidence", "findings": []})
    did, _search, st = _setup(repo, p, tmp_path)
    out = findings.extract(repo, p, did, USER, settings=st)
    assert out["findings"] == [] and out["rejected"] == []


def test_constat_tricheur_rejete(repo, tmp_path):
    def liar(prompt, schema):
        return {"status": "ok", "findings": [
            {"text": "Le budget atteint 98765 euros.", "theme": "x", "severity": "high",
             "sources": ["P1"]}]}

    p = FakeProvider(handler=liar)
    did, _search, st = _setup(repo, p, tmp_path)
    out = findings.extract(repo, p, did, USER, settings=st)
    assert out["findings"] == [] and out["rejected"]
    assert repo.list_findings(did) == []
