"""Lot A « cœur métier » (API) : rôles de documents, priorités, projets, génération liée, cohérence."""

import re
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.config import get_settings
from app.llm import FakeProvider
from app.main import create_app
from tests.services.test_generation_fakes import _scores, honest

V1 = "/api/v1"
DIAG = ("Rapport d'audit\n\nLe processus de paie repose sur quatre tableurs manuels sans contrôle "
        "croisé, ce qui expose le service financier à des erreurs récurrentes.\n")
OTHER = ("Note interne\n\nLa direction souhaite harmoniser les outils de gestion dans les "
         "meilleurs délais pour les services régionaux.\n")
TRAME = "Trame de rapport\n\nInsérer ici le plan type du rapport avec les rubriques usuelles.\n"


class Spy(FakeProvider):
    """Faux modèle : reçoit des handlers, garde les prompts."""


def handler_with_links(prompt, schema):
    if schema.__name__ != "LLMInitiatives":
        return honest(prompt, schema)
    return {"initiatives": [
        {"title": "Automatiser la paie", "description": "d", "findings": ["F1", "F9"],
         "scores": _scores(5), "objective": "Fiabiliser la paie", "expected_result": "Zéro erreur",
         "indicator": "Taux d'erreur", "priorities": ["PR1", "PR9"],
         "depends_on_projects": ["PJ1", "PJ7"]},
        {"title": "Former les équipes", "description": "d", "findings": ["F1"],
         "scores": _scores(2), "priorities": ["PR1"],
         "depends_on_titles": ["Automatiser la paie", "Initiative fantôme"]}]}


@pytest.fixture
def make(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    get_settings.cache_clear()
    clients = []

    def build(provider):
        c = TestClient(create_app(provider, repo))
        c.__enter__()
        clients.append(c)
        return c

    yield build
    for c in clients:
        c.__exit__(None, None, None)
    get_settings.cache_clear()


def new_dossier(c):
    return c.post(f"{V1}/dossiers", json={"name": "D", "client_name": "C"}).json()["id"]


def upload(c, did, name, body, role=None):
    data = {"role": role} if role else None
    r = c.post(f"{V1}/dossiers/{did}/documents", files={"file": (name, body.encode())}, data=data)
    assert r.status_code == 201, r.text
    return r.json()


def roles(c, did):
    return {d["filename"]: d["role"] for d in c.get(f"{V1}/dossiers/{did}/documents").json()}


# 1. rôle de document ------------------------------------------------------------------------
def test_document_role_default_import_and_change(make):
    c = make(FakeProvider(handler=honest))
    did = new_dossier(c)
    a = upload(c, did, "a.txt", DIAG, "diagnostic")
    upload(c, did, "b.txt", OTHER)
    upload(c, did, "c.txt", TRAME, "template")
    assert a["role"] == "diagnostic"
    assert roles(c, did) == {"a.txt": "diagnostic", "b.txt": "other", "c.txt": "template"}
    r = c.patch(f"{V1}/documents/{a['document_id']}", json={"role": "strategy"})
    assert r.status_code == 200 and r.json()["role"] == "strategy"
    bad = c.patch(f"{V1}/documents/{a['document_id']}", json={"role": "poubelle"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "BAD_ROLE"
    r = c.post(f"{V1}/dossiers/{did}/documents", data={"role": "nope"},
               files={"file": ("z.txt", b"Un autre texte assez long pour passer.")})
    assert r.status_code == 422
    assert c.patch(f"{V1}/documents/doc_x", json={"role": "other"}).status_code == 404


def test_many_diagnostics_no_limit(make):
    c = make(FakeProvider(handler=honest))
    did = new_dossier(c)
    for i in range(12):
        upload(c, did, f"audit{i}.txt", f"Audit {i}\n\nConstat numéro {i} sur le périmètre {i * 7}.\n",
               "diagnostic")
    assert list(roles(c, did).values()).count("diagnostic") == 12


# 2. extraction : diagnostics d'abord, trame jamais -----------------------------------------------
def test_findings_read_diagnostics_first_and_never_templates(make):
    prov = FakeProvider(handler=honest)
    c = make(prov)
    did = new_dossier(c)
    upload(c, did, "b.txt", OTHER)  # importé en premier, rôle « other »
    upload(c, did, "t.txt", TRAME, "template")
    upload(c, did, "a.txt", DIAG, "diagnostic")  # importé en dernier
    r = c.post(f"{V1}/dossiers/{did}/findings:extract").json()
    prompts = [x["prompt"] for x in prov.calls if x.get("schema") == "LLMFindings"]
    assert "paie" in prompts[0] and "harmoniser" in prompts[1]
    assert not any("plan type du rapport" in p for p in prompts)
    assert r["coverage"] == {"documents": 2, "chunks_read": 2, "chunks_total": 2}


def test_search_excludes_templates_and_reserves_places(make):
    c = make(FakeProvider(handler=honest))
    did = new_dossier(c)
    upload(c, did, "t.txt", TRAME, "template")
    upload(c, did, "b.txt", OTHER)
    hits = c.post(f"{V1}/dossiers/{did}/search", json={"texts": ["plan type du rapport"], "k": 5}
                  ).json()
    assert all("plan type du rapport" not in h["chunk"]["text"] for h in hits)
    upload(c, did, "a.txt", DIAG, "diagnostic")
    hits = c.post(f"{V1}/dossiers/{did}/search", json={"texts": ["harmoniser les outils"], "k": 3}
                  ).json()
    texts = " ".join(h["chunk"]["text"] for h in hits)
    assert "harmoniser" in texts and "paie" in texts  # le diagnostic a sa place, l'autre reste


# 3. priorités --------------------------------------------------------------------------------------
def test_priority_crud_and_validation_flow(make):
    c = make(FakeProvider(handler=honest))
    did = new_dossier(c)
    up = upload(c, did, "a.txt", DIAG, "diagnostic")
    chunk = c.post(f"{V1}/dossiers/{did}/search", json={"texts": ["paie"], "k": 1}).json()[0]["chunk"]
    assert up["chunks"] == 1
    r = c.post(f"{V1}/dossiers/{did}/priorities",
               json={"title": "Fiabiliser la paie", "description": "Priorité DG",
                     "source_ids": [chunk["id"]]})
    assert r.status_code == 201
    p = r.json()
    assert (p["status"], p["rank"], p["author_id"]) == ("proposed", 1, "usr_dev")
    assert p["created_at"] and p["source_ids"] == [chunk["id"]]
    second = c.post(f"{V1}/dossiers/{did}/priorities", json={"title": "Autre"}).json()
    assert second["rank"] == 2
    bad = c.post(f"{V1}/dossiers/{did}/priorities", json={"title": "X", "source_ids": ["chk_x"]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "UNKNOWN_SOURCE"
    ok = c.patch(f"{V1}/priorities/{p['id']}", json={"status": "validated"}).json()
    assert ok["status"] == "validated"
    edited = c.patch(f"{V1}/priorities/{p['id']}", json={"title": "Fiabiliser la paie 2026"}).json()
    assert edited["status"] == "proposed"  # un texte modifié se revalide
    assert [x["id"] for x in c.get(f"{V1}/dossiers/{did}/priorities").json()] == [p["id"],
                                                                                 second["id"]]
    assert c.delete(f"{V1}/priorities/{second['id']}").status_code == 204
    assert len(c.get(f"{V1}/dossiers/{did}/priorities").json()) == 1
    assert c.get(f"{V1}/dossiers/dos_x/priorities").status_code == 404
    assert c.patch(f"{V1}/priorities/prt_x", json={"status": "validated"}).status_code == 404


def test_priorities_do_not_leak_between_dossiers(make):
    c = make(FakeProvider(handler=honest))
    d1, d2 = new_dossier(c), new_dossier(c)
    c.post(f"{V1}/dossiers/{d1}/priorities", json={"title": "A"})
    assert c.get(f"{V1}/dossiers/{d2}/priorities").json() == []


# 4. projets ------------------------------------------------------------------------------------
def test_project_crud_and_dependencies(make):
    c = make(FakeProvider(handler=honest))
    did = new_dossier(c)
    a = c.post(f"{V1}/dossiers/{did}/projects", json={"title": "Socle SI"}).json()
    assert (a["state"], a["duration_weeks"], a["depends_on"]) == ("existing", None, [])
    b = c.post(f"{V1}/dossiers/{did}/projects",
               json={"title": "Portail", "state": "planned", "duration_weeks": 12,
                     "depends_on": [a["id"]]}).json()
    assert b["depends_on"] == [a["id"]] and b["duration_weeks"] == 12
    cyc = c.patch(f"{V1}/projects/{a['id']}", json={"depends_on": [b["id"]]})
    assert cyc.status_code == 422 and cyc.json()["error"]["code"] == "DEPENDENCY_CYCLE"
    selfdep = c.patch(f"{V1}/projects/{a['id']}", json={"depends_on": [a["id"]]})
    assert selfdep.status_code == 422
    unknown = c.post(f"{V1}/dossiers/{did}/projects", json={"title": "Z", "depends_on": ["prj_x"]})
    assert unknown.status_code == 422
    assert c.patch(f"{V1}/projects/{b['id']}", json={"state": "in_progress"}).json()["state"] == \
        "in_progress"
    assert c.patch(f"{V1}/projects/{b['id']}", json={"duration_weeks": None}).json()[
        "duration_weeks"] is None
    assert c.delete(f"{V1}/projects/{a['id']}").status_code == 204
    assert c.get(f"{V1}/dossiers/{did}/projects").json()[0]["depends_on"] == []
    assert c.post(f"{V1}/dossiers/{did}/projects", json={"title": "Q", "state": "bizarre"}
                  ).status_code == 422


# 5. initiatives : seuls les identifiants fournis ----------------------------------------------
def prepare(c, with_links=True):
    did = new_dossier(c)
    upload(c, did, "a.txt", DIAG, "diagnostic")
    upload(c, did, "b.txt", OTHER)
    c.post(f"{V1}/dossiers/{did}/findings:extract")
    for f in c.get(f"{V1}/dossiers/{did}/findings").json():
        c.patch(f"/api/v1/findings/{f['id']}", json={"validated": True})
    out = {"did": did}
    if with_links:
        out["prio"] = c.post(f"{V1}/dossiers/{did}/priorities",
                             json={"title": "Fiabiliser la paie", "status": "validated"}).json()
        c.post(f"{V1}/dossiers/{did}/priorities", json={"title": "Brouillon non retenu"})
        out["rej"] = c.post(f"{V1}/dossiers/{did}/priorities",
                            json={"title": "Priorité écartée", "status": "rejected"}).json()
        out["proj"] = c.post(f"{V1}/dossiers/{did}/projects",
                             json={"title": "Socle SI", "state": "in_progress"}).json()
    return out


def test_generation_uses_only_provided_ids_and_reports_the_rest(make):
    prov = FakeProvider(handler=handler_with_links)
    c = make(prov)
    w = prepare(c)
    r = c.post(f"{V1}/dossiers/{w['did']}/roadmap:generate", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    prompt = next(x["prompt"] for x in prov.calls if x.get("schema") == "LLMInitiatives")
    assert "PR1:" in prompt and "Fiabiliser la paie" in prompt and "PJ1:" in prompt
    assert "Brouillon non retenu" not in prompt and "Priorité écartée" not in prompt
    items = {i["initiative"]["title"]: i["initiative"] for i in body["roadmap"]["items"]}
    paie, form = items["Automatiser la paie"], items["Former les équipes"]
    assert paie["priority_ids"] == [w["prio"]["id"]] and paie["depends_on_projects"] == [w["proj"]["id"]]
    assert (paie["objective"], paie["expected_result"], paie["indicator"]) == (
        "Fiabiliser la paie", "Zéro erreur", "Taux d'erreur")
    assert form["depends_on"] == [paie["id"]]
    rej = {(x["kind"], x["value"]) for x in body["roadmap"]["rejected_links"]}
    assert rej == {("finding", "F9"), ("priority", "PR9"), ("project", "PJ7"),
                   ("initiative", "Initiative fantôme")}
    assert all(not str(v).startswith("F9") for i in items.values() for v in i["finding_ids"])
    # la cohérence est renvoyée et relisible ; les chaînes pointent vers les passages sources
    coh = body["coherence"]
    assert coh == c.get(f"{V1}/deliverables/{body['deliverable_id']}/coherence").json()
    chain = next(x for x in coh["chains"] if x["initiative_id"] == paie["id"])
    assert chain["priorities"][0]["id"] == w["prio"]["id"] and chain["source_ids"]
    assert any(i["code"] == "NO_DURATION" for i in coh["issues"])  # durée absente : ordre seulement
    assert all(s["start_week"] is None for s in coh["sequence"])


def test_roadmap_patch_links_and_coherence_follow_live_data(make):
    c = make(FakeProvider(handler=handler_with_links))
    w = prepare(c)
    body = c.post(f"{V1}/dossiers/{w['did']}/roadmap:generate", json={}).json()
    dlv = body["deliverable_id"]
    ids = {i["initiative"]["title"]: i["initiative"]["id"] for i in body["roadmap"]["items"]}
    bad = c.patch(f"{V1}/deliverables/{dlv}/roadmap",
                  json={"initiatives": [{"id": ids["Former les équipes"], "priority_ids": ["prt_x"]}]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "BAD_PRIORITY"
    bad = c.patch(f"{V1}/deliverables/{dlv}/roadmap",
                  json={"initiatives": [{"id": ids["Former les équipes"],
                                         "depends_on_projects": ["prj_x"]}]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "BAD_PROJECT"
    ok = c.patch(f"{V1}/deliverables/{dlv}/roadmap", json={"initiatives": [
        {"id": ids["Former les équipes"], "duration_weeks": 2, "indicator": "Heures dispensées"},
        {"id": ids["Automatiser la paie"], "duration_weeks": 6}]})
    assert ok.status_code == 200
    seq = {s["initiative_id"]: s for s in ok.json()["coherence"]["sequence"]}
    assert seq[ids["Automatiser la paie"]]["end_week"] == 6
    assert seq[ids["Former les équipes"]]["start_week"] == 6  # après son prérequis
    # rejeter la priorité APRÈS coup : la cohérence le voit aussitôt (sans nouvelle génération)
    c.patch(f"{V1}/priorities/{w['prio']['id']}", json={"status": "rejected"})
    now = c.get(f"{V1}/deliverables/{dlv}/coherence").json()
    assert {i["code"] for i in now["issues"]} >= {"INITIATIVE_UNANCHORED"}


def test_generation_without_priorities_or_projects_still_works(make):
    c = make(FakeProvider(handler=honest))
    w = prepare(c, with_links=False)
    body = c.post(f"{V1}/dossiers/{w['did']}/roadmap:generate", json={}).json()
    codes = {i["code"] for i in body["coherence"]["issues"]}
    assert "INITIATIVE_UNANCHORED" in codes  # sans priorité validée : signalé, pas caché


def test_generation_refuses_when_context_cannot_hold_priorities_and_projects(make):
    prov = FakeProvider(handler=honest)
    prov.context_tokens = 1500
    c = make(prov)
    w = prepare(c, with_links=False)
    for i in range(40):  # priorités validées nombreuses : elles ne tiennent plus
        c.post(f"{V1}/dossiers/{w['did']}/priorities",
               json={"title": f"Priorité institutionnelle numéro {i} " + "mot " * 30,
                     "status": "validated"})
    r = c.post(f"{V1}/dossiers/{w['did']}/roadmap:generate", json={})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONTEXT_FULL"
    assert "Rien n'a été coupé" in r.json()["error"]["message"]
    assert not any(x.get("schema") == "LLMInitiatives" for x in prov.calls)


def test_passages_not_sent_are_reported(make):
    prov = FakeProvider(handler=honest)
    prov.context_tokens = 2000
    c = make(prov)
    did = new_dossier(c)
    for i in range(8):
        upload(c, did, f"d{i}.txt", f"Audit {i}\n\nConstat {i} : " + ("service numérique dispersé " * 20),
               "diagnostic")
    from app.domain.generation import Finding
    repo = c.app.state.repo
    chunks = [ch.id for ch in repo.iter_chunks(did)]
    repo.save_findings(did, [Finding(id=f"fnd_{i}", dossier_id=did, text=f"c{i}", theme="t",
                                     severity="low", source_ids=[chunks[i]], validated=True)
                             for i in range(len(chunks))])
    body = c.post(f"{V1}/dossiers/{did}/roadmap:generate", json={}).json()
    sent = len(re.findall(r"<<PASSAGE id=", next(x["prompt"] for x in prov.calls
                                                  if x.get("schema") == "LLMInitiatives")))
    assert body["roadmap"]["passages_not_sent"] == len(chunks) - sent > 0


# migration ---------------------------------------------------------------------------------------
def test_migration_0003_up_and_down(tmp_path):
    from tests.storage.test_engine_migrations import ROOT

    url = f"sqlite+pysqlite:///{(tmp_path / 'm.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.cmd_opts = SimpleNamespace(x=[f"url={url}"])
    command.upgrade(cfg, "0002")
    command.upgrade(cfg, "0003")
    eng = create_engine(url)
    insp = inspect(eng)
    assert {"priorities", "existing_projects"} <= set(insp.get_table_names())
    assert "role" in {c["name"] for c in insp.get_columns("documents")}
    command.downgrade(cfg, "0002")
    insp = inspect(create_engine(url))
    assert not {"priorities", "existing_projects"} & set(insp.get_table_names())
    assert "role" not in {c["name"] for c in insp.get_columns("documents")}
    command.upgrade(cfg, "head")  # remontée possible
    assert "role" in {c["name"] for c in inspect(create_engine(url)).get_columns("documents")}


def test_old_database_without_role_column_gets_it(tmp_path):
    """Base créée avant 0003 : la colonne est ajoutée, les documents existants valent « other »."""
    from sqlalchemy import text

    from tests.storage.test_engine_migrations import ROOT

    url = f"sqlite+pysqlite:///{(tmp_path / 'old.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.cmd_opts = SimpleNamespace(x=[f"url={url}"])
    command.upgrade(cfg, "0002")
    eng = create_engine(url)
    with eng.begin() as conn:  # simule une base antérieure : colonne absente, un document présent
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("ALTER TABLE documents DROP COLUMN role"))
        conn.execute(text("INSERT INTO users (id,email,display_name,password_hash,role,created_at,"
                          "active) VALUES ('u','e','n','h','admin','2026-01-01',1)"))
        conn.execute(text("INSERT INTO dossiers (id,name,client_name,language,owner_id,created_at,"
                          "archived,is_demo) VALUES ('d','n','c','fr','u','2026-01-01',0,0)"))
        conn.execute(text("INSERT INTO documents (id,dossier_id,filename,mime,sha256,stored_path,"
                          "created_at) VALUES ('x','d','f','m','s','p','2026-01-01')"))
    command.upgrade(cfg, "0003")
    with eng.connect() as conn:
        assert conn.execute(text("SELECT role FROM documents WHERE id='x'")).scalar() == "other"
