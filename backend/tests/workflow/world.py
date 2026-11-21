"""Monde de test D1 : mode « token », 3 utilisateurs, 2 dossiers, un livrable ancré."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth.passwords import hash_password
from app.config import Settings, get_settings
from app.domain.documents import Chunk, ParsedDocument
from app.domain.generation import DeliverableContent, SectionDraft, Sentence
from app.llm import FakeProvider
from app.main import create_app
from app.storage import build_repository

PASSWORD = "mot-de-passe-test-1"
CHUNK_TEXT = "Le comité de pilotage se réunit chaque mois pour suivre la feuille de route."


def make_content(chunk_id: str, text: str = CHUNK_TEXT, status="ok", sentences=None):
    sents = sentences if sentences is not None else [
        Sentence(text=text, kind="fact", source_labels=["P1"], source_ids=[chunk_id])]
    return DeliverableContent(
        type="findings", language="fr", template_id="findings", template_version="1",
        sections=[SectionDraft(section_key="constats", status=status, sentences=sents)])


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "token")
    monkeypatch.setenv("ALLOW_SELF_APPROVAL", "false")
    get_settings.cache_clear()
    url = f"sqlite+pysqlite:///{(tmp_path / 'w.db').as_posix()}"
    repo = build_repository(Settings(storage_url=url, auth_mode="token"))
    h = hash_password(PASSWORD)
    alice = repo.create_user("alice@ex.test", "Alice", h, "consultant")
    bob = repo.create_user("bob@ex.test", "Bob", h, "reviewer")
    carol = repo.create_user("carol@ex.test", "Carol", h, "consultant")
    root = repo.create_user("root@ex.test", "Root", h, "admin")
    dos = repo.create_dossier("D1", "Client", "fr", alice)
    repo.add_member(dos, alice, "consultant")
    repo.add_member(dos, bob, "reviewer")
    other = repo.create_dossier("D2", "Autre", "fr", carol)
    repo.add_member(other, carol, "consultant")
    parsed = ParsedDocument(filename="a.txt", mime="text/plain", sha256="a" * 64, title=None,
                            language="fr", blocks=[])
    doc = repo.add_document(dos, parsed, "x")
    chunk = Chunk(id="chk_test00000001", document_id=doc, dossier_id=dos, ordinal=0,
                  text=CHUNK_TEXT, page_start=1, page_end=1, section_path=(), token_estimate=14)
    repo.add_chunks([chunk], [[0.0] * 64], "fake")
    dlv = repo.create_deliverable(dos, "findings", "findings", alice)
    repo.add_version(dlv, make_content(chunk.id), alice, "generated")
    with TestClient(create_app(FakeProvider(), repo)) as client:
        def login(email):
            r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
            assert r.status_code == 200, r.text
            return {"Authorization": f"Bearer {r.json()['token']}"}

        yield SimpleNamespace(
            client=client, repo=repo, login=login, dossier=dos, other=other, chunk=chunk,
            deliverable=dlv, alice=alice, bob=bob, carol=carol, root=root,
            h_alice=login("alice@ex.test"), h_bob=login("bob@ex.test"),
            h_carol=login("carol@ex.test"))
    get_settings.cache_clear()
