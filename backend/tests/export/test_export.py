"""Tests du lot D2 : exports DOCX / PPTX / PDF, garde d'approbation, route."""

import re

import pytest
from docx import Document
from pptx import Presentation

from app.config import get_settings
from app.domain.documents import Block, Chunk, ParsedDocument
from app.domain.generation import DeliverableContent, SectionDraft, Sentence
from app.domain.roadmap import (
    Criterion,
    CriterionScore,
    Initiative,
    RoadmapResult,
    ScoredInitiative,
)
from app.export.common import (
    ExportForbidden,
    build_export_data,
    export_deliverable,
    load_export_data,
)
from app.export.pdf_export import soffice_binary

P = "/api/v1"


def _roadmap() -> RoadmapResult:
    def ini(i, deps=(), weeks=None):
        return Initiative(
            id=f"ini_{i}", title=f"Initiative {i}", description="d", finding_ids=[f"F{i}", "F9"],
            scores=[CriterionScore(key="impact", value=i, source_ids=[], rationale="r"),
                    CriterionScore(key="faisabilite", value=5 - i, source_ids=[], rationale="r")],
            depends_on=list(deps), duration_weeks=weeks)

    items = [ScoredInitiative(initiative=ini(1, weeks=6), score=4.2, rank=1, wave=1),
             ScoredInitiative(initiative=ini(2), score=3.1, rank=2, wave=2),
             ScoredInitiative(initiative=ini(3, weeks=3), score=2.0, rank=3, wave=3)]
    return RoadmapResult(
        criteria=[Criterion(key="impact", label="Impact", weight=0.5),
                  Criterion(key="faisabilite", label="Faisabilité", weight=0.5)],
        items=items, topo_order=[], cycles=[], critical_path=[])


@pytest.fixture
def world(repo):
    uid = repo.create_user("c@x.fr", "C", "h", "consultant")
    dos = repo.create_dossier("D", "Client", "fr", uid)
    doc = repo.add_document(
        dos, ParsedDocument(filename="rapport.pdf", mime="application/pdf", sha256="a" * 64, title="R",
                            language="fr", blocks=[Block(text="x", page=1)]), "/p")
    chunks = [Chunk(id=f"chk_{i}", document_id=doc, dossier_id=dos, ordinal=i,
                    text=("Texte long. " * 40) if i == 1 else f"Passage {i}.", page_start=i, page_end=i,
                    section_path=("Intro",), token_estimate=5) for i in (1, 2, 3)]
    repo.add_chunks(chunks, [[1.0, 0.0]] * 3, "fake")
    content = DeliverableContent(
        type="tor", language="fr", template_id="tor-fr-standard", template_version="1.0",
        sections=[
            SectionDraft(section_key="contexte", status="ok", sentences=[
                Sentence(text="Première phrase.", kind="fact", source_ids=["chk_2", "chk_1"]),
                Sentence(text="Deuxième phrase.", kind="fact", source_ids=["chk_2", "chk_3"])]),
            SectionDraft(section_key="objectifs", status="insufficient_evidence", sentences=[],
                         missing_evidence="rien")])
    from app.domain.generation import Finding
    repo.save_findings(dos, [Finding(id=f, dossier_id=dos, text="Constat.", theme="t", severity="high",
                                     source_ids=["chk_2"], validated=True) for f in ("F1", "F2", "F3", "F9")])
    did = repo.create_deliverable(dos, "tor", "tor-fr-standard", uid)
    repo.add_version(did, content, uid, "generated")
    return {"repo": repo, "uid": uid, "dos": dos, "did": did, "content": content}


def _approve(w):
    w["repo"].set_state(w["did"], "approved", w["uid"], None)


def test_citations_ordre_apparition_et_sources(world):
    _approve(world)
    data = load_export_data(world["repo"], world["did"])
    assert [x.n for x in data.sources] == [1, 2, 3]
    assert data.sources[0].excerpt == "Passage 2."  # chk_2 cité en premier
    assert len(data.sources[1].excerpt) <= 200 and data.sources[1].excerpt.endswith("…")
    assert data.sections[0].sentences[0].rendered == "Première phrase. [1] [2]"
    assert data.sections[0].sentences[1].numbers == [1, 3]
    assert data.sources[0].document == "rapport.pdf" and data.sources[0].page == "2"
    assert re.fullmatch(r"[0-9a-f]{64}", data.sha256)


def test_docx_titres_citations_annexe_pied(world, tmp_path):
    _approve(world)
    path, digest = export_deliverable(world["repo"], world["did"], "docx", world["uid"], tmp_path)
    doc = Document(str(path))
    heads = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert "Contexte et justification" in heads and "Sources" in heads
    body = "\n".join(p.text for p in doc.paragraphs)
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", body)}
    annex = doc.tables[-1]
    assert len(annex.rows) - 1 == len(cited) == 3
    footer = doc.sections[0].footer.paragraphs[0].text
    assert "Version 1" in footer and "SHA-256" in footer and world["uid"] in footer
    assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_docx_feuille_de_route(world, tmp_path):
    repo, rm = world["repo"], _roadmap()
    c = world["content"].model_copy(update={"type": "roadmap", "roadmap": rm})
    repo.add_version(world["did"], c, world["uid"], "edited")
    _approve(world)
    path, _ = export_deliverable(repo, world["did"], "docx", world["uid"], tmp_path)
    doc = Document(str(path))
    assert len(doc.tables) == 3  # initiatives, matrice, sources
    assert len(doc.tables[0].rows) == 4 and len(doc.tables[1].rows) == 5  # F1,F2,F3,F9


def test_pptx_diapositives_et_vagues(world, tmp_path):
    repo = world["repo"]
    c = world["content"].model_copy(update={"type": "roadmap", "roadmap": _roadmap()})
    repo.add_version(world["did"], c, world["uid"], "edited")
    _approve(world)
    path, _ = export_deliverable(repo, world["did"], "pptx", world["uid"], tmp_path)
    prs = Presentation(str(path))
    titles = [s.shapes.title.text for s in prs.slides if s.shapes.title is not None]
    assert len(prs.slides) >= 2
    assert sum(t.startswith("Vague") for t in titles) == 3
    assert any("Gantt" in t for t in titles) and any("Matrice" in t for t in titles)


def test_export_non_approuve_interdit(world, tmp_path):
    with pytest.raises(ExportForbidden):
        export_deliverable(world["repo"], world["did"], "docx", world["uid"], tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_journal_et_table_exports(world, tmp_path):
    from sqlalchemy import select

    from app.storage import schema as s

    _approve(world)
    export_deliverable(world["repo"], world["did"], "docx", world["uid"], tmp_path)
    with world["repo"].engine.connect() as c:
        assert c.execute(select(s.exports.c.format)).scalar() == "docx"
        assert c.execute(select(s.audit_log.c.action).where(s.audit_log.c.action == "export")).scalar() == "export"


def test_route_403_puis_200_docx(world, client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    get_settings.cache_clear()
    # le dossier de `world` a été créé par un autre utilisateur : on s'ajoute comme membre
    world["repo"].add_member(world["dos"], "usr_dev", "consultant")
    url = f"{P}/deliverables/{world['did']}/exports"
    r = client.post(url, json={"format": "docx"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "EXPORT_FORBIDDEN"
    _approve(world)
    r = client.post(url, json={"format": "docx"})
    assert r.status_code == 200 and r.content[:2] == b"PK" and len(r.headers["x-content-sha256"]) == 64
    assert client.post(url, json={"format": "odt"}).status_code == 422
    assert client.post(f"{P}/deliverables/inconnu/exports", json={}).status_code == 404


def test_route_pdf_501_sans_soffice(world, client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    get_settings.cache_clear()
    monkeypatch.setattr("app.export.pdf_export.soffice_binary", lambda: None)
    world["repo"].add_member(world["dos"], "usr_dev", "consultant")
    _approve(world)
    r = client.post(f"{P}/deliverables/{world['did']}/exports", json={"format": "pdf"})
    assert r.status_code == 501 and r.json()["error"]["code"] == "EXPORT_UNAVAILABLE"


@pytest.mark.soffice
@pytest.mark.skipif(soffice_binary() is None, reason="LibreOffice absent")
def test_pdf_soffice(world, tmp_path):
    _approve(world)
    path, _ = export_deliverable(world["repo"], world["did"], "pdf", world["uid"], tmp_path)
    assert path.read_bytes()[:4] == b"%PDF"


def test_build_export_data_refuse_source_inconnue():
    """Une citation invalide n'est jamais effacée en silence : l'export est refusé."""
    c = DeliverableContent(type="tor", language="fr", template_id="t", template_version="1", sections=[
        SectionDraft(section_key="a", status="ok", sentences=[Sentence(text="x", kind="fact", source_ids=["zzz"])])])
    with pytest.raises(ExportForbidden):
        build_export_data(c, {}, {}, deliverable_id="d", version=1, approver="u", approved_at="2026-01-01")
