"""Lot B : API des décisions humaines et migration 0004."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

V1 = "/api/v1"


def _dossier(client) -> str:
    return client.post(f"{V1}/dossiers", json={"name": "D", "client_name": "C"}).json()["id"]


def test_cycle_de_vie_d_une_decision(client):
    did = _dossier(client)
    r = client.post(f"{V1}/dossiers/{did}/decisions",
                    json={"category": "budget", "text": "Enveloppe de 40 000 euros."})
    assert r.status_code == 201
    d = r.json()
    assert d["status"] == "proposed" and d["confirmed_at"] is None and d["author_name"]
    c = client.post(f"{V1}/decisions/{d['id']}:confirm").json()
    assert c["status"] == "confirmed" and c["confirmed_at"] and c["confirmed_by_name"]
    # modifier une décision confirmée la repasse « proposée » : à reconfirmer
    p = client.patch(f"{V1}/decisions/{d['id']}", json={"text": "Enveloppe de 50 000 euros."}).json()
    assert p["status"] == "proposed" and p["confirmed_at"] is None
    assert client.post(f"{V1}/decisions/{d['id']}:retract").json()["status"] == "proposed"
    assert len(client.get(f"{V1}/dossiers/{did}/decisions").json()) == 1
    assert client.delete(f"{V1}/decisions/{d['id']}").status_code == 204
    assert client.get(f"{V1}/dossiers/{did}/decisions").json() == []


def test_categorie_et_texte_valides(client):
    did = _dossier(client)
    bad = client.post(f"{V1}/dossiers/{did}/decisions", json={"category": "magie", "text": "x"})
    assert bad.status_code == 422
    blank = client.post(f"{V1}/dossiers/{did}/decisions", json={"category": "budget", "text": "  "})
    assert blank.status_code == 422
    assert client.post(f"{V1}/dossiers/dos_inconnu/decisions",
                       json={"category": "budget", "text": "x"}).status_code == 404


def test_audit_des_decisions(client, repo):
    did = _dossier(client)
    d = client.post(f"{V1}/dossiers/{did}/decisions",
                    json={"category": "profile", "text": "Chef de projet."}).json()
    client.post(f"{V1}/decisions/{d['id']}:confirm")
    from app.workflow import versions as vs

    actions = [a["action"] for a in vs.list_audit(repo, d["id"])]
    assert actions == ["decision.create", "decision.confirm"]


def test_migration_0004_montee_et_descente(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'm.db').as_posix()}"
    from types import SimpleNamespace

    from tests.storage.test_engine_migrations import ROOT

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.cmd_opts = SimpleNamespace(x=[f"url={url}"])
    command.upgrade(cfg, "0003")
    eng = create_engine(url)
    assert "decisions" not in inspect(eng).get_table_names()
    command.upgrade(cfg, "0004")
    names = set(inspect(eng).get_table_names())
    assert {"decisions", "context_sheets"} <= names
    command.downgrade(cfg, "0003")
    names = set(inspect(eng).get_table_names())
    assert not {"decisions", "context_sheets"} & names and "priorities" in names
    command.upgrade(cfg, "head")
    assert "decisions" in set(inspect(eng).get_table_names())
