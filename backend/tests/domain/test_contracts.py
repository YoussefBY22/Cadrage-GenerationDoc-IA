"""Chaque contrat se construit, se sérialise en JSON et expose un schéma JSON."""

import pytest
from pydantic import BaseModel, ValidationError

from app.domain import documents, generation, retrieval, roadmap, verification, workflow
from app.domain.ids import new_id

CHUNK = documents.Chunk(
    id="chk_1", document_id="doc_1", dossier_id="dos_1", ordinal=0, text="Texte",
    page_start=1, page_end=2, section_path=("2. Diagnostic", "2.1 Gouvernance"),
    token_estimate=3)
CRIT = roadmap.Criterion(key="impact", label="Impact", weight=0.35)
INIT = roadmap.Initiative(
    id="ini_1", title="T", description="D", finding_ids=["fnd_1"],
    scores=[roadmap.CriterionScore(key="impact", value=5, source_ids=["chk_1"], rationale="r")])
ROAD = roadmap.RoadmapResult(
    criteria=[CRIT], items=[roadmap.ScoredInitiative(initiative=INIT, score=1.0, rank=1, wave=1)],
    topo_order=["ini_1"], cycles=[], critical_path=["ini_1"])
SENT = generation.Sentence(text="Phrase.", kind="fact", source_labels=["P1"], source_ids=["chk_1"])
SECTION = generation.SectionDraft(section_key="s", status="ok", sentences=[SENT])

INSTANCES: list[BaseModel] = [
    documents.Block(text="t", page=None),
    documents.ParsedDocument(filename="a.txt", mime="text/plain", sha256="0" * 64, title=None,
                             language="fr", blocks=[documents.Block(text="t", page=1)]),
    CHUNK,
    retrieval.Passage(label="P1", chunk=CHUNK, score=0.5, ranks={"bm25": 1}),
    retrieval.SearchQuery(dossier_id="dos_1", texts=["q"]),
    SENT,
    SECTION,
    generation.Finding(id="fnd_1", dossier_id="dos_1", text="t", theme="x", severity="high",
                       source_ids=["chk_1"]),
    generation.DeliverableContent(type="roadmap", language="fr", template_id="t",
                                  template_version="1", sections=[SECTION], roadmap=ROAD),
    verification.Issue(sentence_index=0, code="LOW_SUPPORT", severity="warning", detail="d"),
    verification.SentenceCheck(index=0, status="verified", numbers_cited=0, numbers_found=0,
                               support=1.0),
    verification.VerificationReport(section_key="s", checks=[], issues=[]),
    CRIT, roadmap.CriterionScore(key="k", value=1, source_ids=[], rationale=""), INIT,
    roadmap.ScoredInitiative(initiative=INIT, score=0.1, rank=1, wave=1), ROAD,
    workflow.Transition(to="rejected", reason="motif"),
    workflow.CurrentUser(id="usr_dev", role="admin"),
]


@pytest.mark.parametrize("obj", INSTANCES, ids=lambda o: type(o).__name__)
def test_json_roundtrip_and_schema(obj):
    cls = type(obj)
    assert cls.model_validate_json(obj.model_dump_json()) == obj
    assert cls.model_json_schema()


def test_models_are_frozen():
    with pytest.raises(ValidationError):
        CHUNK.text = "autre"


def _check(status: str) -> verification.SentenceCheck:
    return verification.SentenceCheck(index=0, status=status, numbers_cited=0, numbers_found=0,
                                      support=0.5)


def test_tpv():
    checks = [_check("verified"), _check("verified"), _check("warning"), _check("failed")]
    assert verification.VerificationReport(section_key="s", checks=checks, issues=[]).tpv == 0.5
    assert verification.VerificationReport(section_key="s", checks=[], issues=[]).tpv == 1.0


def test_new_id():
    a, b = new_id("doc"), new_id("doc")
    assert a.startswith("doc_") and len(a) == 16 and a != b
