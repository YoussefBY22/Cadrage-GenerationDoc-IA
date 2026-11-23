# ruff: noqa: F811
"""Verrou d'approbation : aucune preuve manquante ne s'acquitte, aucun contournement par l'édition."""

import pytest

from app.domain.generation import DeliverableContent, Finding, Sentence
from app.domain.roadmap import Criterion, Initiative, RoadmapResult, ScoredInitiative
from app.export.common import ExportForbidden, load_export_data
from tests.workflow.world import CHUNK_TEXT, make_content, world  # noqa: F401

API = "/api/v1"


def tr(w, headers, to, reason=None, d=None):
    return w.client.post(f"{API}/deliverables/{d or w.deliverable}/transitions",
                         json={"to": to, "reason": reason}, headers=headers)


def put(w, content, headers=None, d=None):
    body = content if isinstance(content, dict) else content.model_dump(mode="json")
    return w.client.put(f"{API}/deliverables/{d or w.deliverable}/content", json=body,
                        headers=headers or w.h_alice)


def ack(w, index=0, reason="vérifié dans le document papier", headers=None, key="constats"):
    body = {"section_key": key, "sentence_index": index}
    if reason is not None:
        body["reason"] = reason
    return w.client.post(f"{API}/deliverables/{w.deliverable}/acknowledgements", json=body,
                         headers=headers or w.h_bob)


def code(r):
    return r.json().get("error", {}).get("code")


def sentence(w, text=CHUNK_TEXT, kind="fact", sources=None, findings=()):
    return Sentence(text=text, kind=kind, source_ids=[w.chunk.id] if sources is None else sources,
                    finding_ids=list(findings))


def finding(w, fid, validated):
    w.repo.save_findings(w.dossier, [Finding(id=fid, dossier_id=w.dossier, text=CHUNK_TEXT, theme="t",
                                             severity="high", source_ids=[w.chunk.id],
                                             validated=validated)])
    return fid


# --- défauts de preuve : jamais acquittables ---------------------------------------------------
@pytest.mark.parametrize("bad", [
    {"sources": ["chk_inexistant"]},                          # UNKNOWN_SOURCE
    {"sources": []},                                          # FACT_WITHOUT_SOURCE
    {"findings": ["fnd_inexistant"]},                         # UNKNOWN_FINDING
])
def test_missing_evidence_cannot_be_acknowledged(world, bad):
    w = world
    assert put(w, make_content(w.chunk.id, sentences=[sentence(w, **bad)])).status_code == 200
    tr(w, w.h_alice, "in_review")
    r = ack(w)
    assert r.status_code == 409 and code(r) == "NOT_ACKNOWLEDGEABLE"
    assert code(tr(w, w.h_bob, "approved")) == "UNACKNOWLEDGED_FAILURES"


def test_foreign_source_cannot_be_acknowledged(world):
    w = world
    other_doc = w.repo.add_document(w.other, __import__("app.domain.documents", fromlist=["x"]).ParsedDocument(
        filename="b.txt", mime="text/plain", sha256="b" * 64, title=None, language="fr", blocks=[]), "y")
    from app.domain.documents import Chunk
    w.repo.add_chunks([Chunk(id="chk_autre", document_id=other_doc, dossier_id=w.other, ordinal=0,
                             text=CHUNK_TEXT, page_start=1, page_end=1, section_path=(),
                             token_estimate=14)], [[0.0] * 64], "fake")
    put(w, make_content(w.chunk.id, sentences=[sentence(w, sources=["chk_autre"])]))
    tr(w, w.h_alice, "in_review")
    assert code(ack(w)) == "NOT_ACKNOWLEDGEABLE"
    assert tr(w, w.h_bob, "approved").status_code == 409


def test_sentence_citing_unvalidated_finding_blocks(world):
    w = world
    fid = finding(w, "fnd_non_valide", validated=False)
    put(w, make_content(w.chunk.id, sentences=[sentence(w, findings=[fid])]))
    tr(w, w.h_alice, "in_review")
    assert code(ack(w)) == "NOT_ACKNOWLEDGEABLE"
    assert code(tr(w, w.h_bob, "approved")) == "UNACKNOWLEDGED_FAILURES"
    ok = finding(w, "fnd_valide", validated=True)
    tr(w, w.h_alice, "draft")
    put(w, make_content(w.chunk.id, sentences=[sentence(w, findings=[ok])]))
    tr(w, w.h_alice, "in_review")
    assert tr(w, w.h_bob, "approved").status_code == 200


# --- acquittement : motif, version, rôle --------------------------------------------------------
def test_acknowledgement_needs_reason(world):
    w = world
    put(w, make_content(w.chunk.id, sentences=[sentence(w, text="Le budget atteint 9 999 euros.")]))
    tr(w, w.h_alice, "in_review")
    assert code(ack(w, reason=None)) == "REASON_REQUIRED"
    assert code(ack(w, reason="   ")) == "REASON_REQUIRED"
    assert ack(w).status_code == 201
    assert tr(w, w.h_bob, "approved").status_code == 200


def test_old_acknowledgement_without_reason_does_not_count(world):
    w = world
    put(w, make_content(w.chunk.id, sentences=[sentence(w, text="Le budget atteint 9 999 euros.")]))
    tr(w, w.h_alice, "in_review")
    w.repo.audit(w.bob, "sentence.acknowledge", "deliverable", w.deliverable,
                 {"version": 2, "section_key": "constats", "sentence_index": 0})  # ancien format
    assert code(tr(w, w.h_bob, "approved")) == "UNACKNOWLEDGED_FAILURES"


def test_author_cannot_acknowledge_own_deliverable(world):
    w = world
    put(w, make_content(w.chunk.id, sentences=[sentence(w, text="Le budget atteint 9 999 euros.")]))
    w.repo.add_member(w.dossier, w.alice, "reviewer")   # auteur ET relecteur
    tr(w, w.h_alice, "in_review")
    r = ack(w, headers=w.h_alice)
    assert r.status_code == 409 and code(r) == "FOUR_EYES"


def test_unsupported_recommendation_needs_acknowledgement(world):
    w = world
    put(w, make_content(w.chunk.id, sentences=[
        sentence(w, text="Il faut remplacer tous les outils.", kind="recommendation", sources=[])]))
    tr(w, w.h_alice, "in_review")
    assert code(tr(w, w.h_bob, "approved")) == "UNACKNOWLEDGED_FAILURES"
    assert ack(w).status_code == 201
    assert tr(w, w.h_bob, "approved").status_code == 200


# --- complétude --------------------------------------------------------------------------------
def test_ok_section_without_sentence_is_incomplete(world):
    w = world
    put(w, make_content(w.chunk.id, sentences=[]))
    tr(w, w.h_alice, "in_review")
    assert code(tr(w, w.h_bob, "approved")) == "INCOMPLETE_SECTIONS"


# --- édition : pas de contournement ------------------------------------------------------------
@pytest.mark.parametrize("change", [
    {"type": "tor"}, {"language": "en"}, {"template_id": "autre"}, {"template_version": "9"}])
def test_edit_cannot_change_identity_of_deliverable(world, change):
    w = world
    body = make_content(w.chunk.id).model_dump(mode="json") | change
    r = put(w, body)
    assert r.status_code == 422 and code(r) == "IDENTITY_CHANGED"


def _roadmap_world(w, finding_ids, items=True):
    did = w.repo.create_deliverable(w.dossier, "roadmap", "roadmap", w.alice)
    ini = Initiative(id="ini_1", title="Initiative", description="d", finding_ids=finding_ids,
                     scores=[])
    road = RoadmapResult(criteria=[Criterion(key="impact", label="Impact", weight=1.0)],
                         items=[ScoredInitiative(initiative=ini, score=1.0, rank=1, wave=1)] if items else [],
                         topo_order=[], cycles=[], critical_path=[])
    w.repo.add_version(did, DeliverableContent(
        type="roadmap", language="fr", template_id="roadmap", template_version="1", sections=[],
        roadmap=road), w.alice, "generated")
    return did


def test_roadmap_content_cannot_be_dropped(world):
    w = world
    did = _roadmap_world(w, [finding(w, "fnd_ok", True)])
    body = w.client.get(f"{API}/deliverables/{did}", headers=w.h_alice).json()["content"]
    r = put(w, body | {"roadmap": None}, d=did)
    assert r.status_code == 422 and code(r) == "ROADMAP_REQUIRED"


@pytest.mark.parametrize("fids", [[], ["fnd_inconnu"], ["fnd_non_valide"]])
def test_roadmap_with_unfounded_initiative_is_not_approvable(world, fids):
    w = world
    finding(w, "fnd_non_valide", validated=False)
    did = _roadmap_world(w, fids)
    tr(w, w.h_alice, "in_review", d=did)
    assert code(tr(w, w.h_bob, "approved", d=did)) == "UNVERIFIED_INITIATIVES"


def test_empty_roadmap_is_not_approvable(world):
    w = world
    did = _roadmap_world(w, [], items=False)
    tr(w, w.h_alice, "in_review", d=did)
    assert code(tr(w, w.h_bob, "approved", d=did)) == "UNVERIFIED_INITIATIVES"


# --- rôles -------------------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["reviewer", "admin"])
def test_owner_cannot_make_self_reviewer(world, role):
    w = world
    r = w.client.post(f"{API}/dossiers/{w.dossier}/members", json={"user_id": w.alice, "role": role},
                      headers=w.h_alice)
    assert r.status_code == 403 and code(r) == "SELF_REVIEWER"


def test_deliverable_author_cannot_approve_after_someone_else_edited(world):
    w = world
    w.repo.add_member(w.dossier, w.alice, "reviewer")
    put(w, make_content(w.chunk.id), headers=w.h_bob)   # bob fait la dernière version
    tr(w, w.h_bob, "in_review")
    assert code(tr(w, w.h_alice, "approved")) == "FOUR_EYES"


# --- export : revérifie, n'efface jamais ------------------------------------------------------
@pytest.mark.parametrize("bad", [{"sources": ["chk_inexistant"]}, {"sources": []},
                                 {"findings": ["fnd_inconnu"]}])
def test_export_rechecks_an_already_approved_deliverable(world, bad):
    w = world
    w.repo.add_version(w.deliverable, make_content(w.chunk.id, sentences=[sentence(w, **bad)]),
                       w.alice, "edited")
    w.repo.set_state(w.deliverable, "approved", w.bob, None)   # approuvé avant ce correctif
    with pytest.raises(ExportForbidden):
        load_export_data(w.repo, w.deliverable)


def test_export_rechecks_initiatives(world):
    w = world
    did = _roadmap_world(w, ["fnd_inconnu"])
    w.repo.set_state(did, "approved", w.bob, None)
    with pytest.raises(ExportForbidden):
        load_export_data(w.repo, did)
