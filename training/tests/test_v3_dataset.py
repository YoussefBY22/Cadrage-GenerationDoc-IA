"""Tests du pilote v3 : licence obligatoire, rendu identique à l'application, vérificateur, séparation par document.

Aucun réseau ni PDF : des documents minuscules sont fabriqués ici. Les contrôles sur le jeu produit
(``training/data/pilote-v3``) ne s'exécutent que si les fichiers existent.
"""

import json
import random
import re
from collections import Counter
from pathlib import Path

import pytest
from app.domain.retrieval import Passage
from app.generation import prompting
from app.generation.template_loader import SectionSpec

from training.dataset import v3_build, v3_curation, v3_text
from training.dataset.v3_sources import SOURCES, check_manifest, source_text

DOC = "doc-test"
TEXT = ("Intro du rapport.\n\n"
        "12 Nous avons constaté que le délai moyen de traitement dépasse un an dans 38 % des dossiers. "
        "Cependant, le service a progressé depuis 2020.\n\n"
        "Recommandation n° 1 – Réduire les délais\n"
        "La Commission devrait réduire les délais:\n"
        "a) en recrutant des agents;\n"
        "b) en suivant chaque dossier.\n"
        "Quand? D'ici à fin 2026.\n\n"
        "Un passage sans rapport sur les locaux du service.\n")
FAKE = {"id": DOC, "titre": "Doc test", "editeur": "Éditeur test", "url": "https://exemple.test/doc.pdf",
        "licence": "CC BY 4.0 (test)", "preuve_url": "https://exemple.test/licence", "preuve_extrait": "CC BY 4.0",
        "test": False}


def _ex(**kw) -> dict:
    base = {"id": "t0", "type": "feuille de route", "doc": DOC, "section": ("roadmap", "initiatives"),
            "passages": [v3_curation.P(DOC, "Nous avons constaté", "depuis 2020."),
                         v3_curation.P(DOC, "Recommandation n° 1 – Réduire", "fin 2026."),
                         v3_curation.P(DOC, "Un passage sans rapport", None)],
            "phrases": [("v", 0, "Nous avons constaté que le délai moyen de traitement dépasse un an dans 38 % des dossiers."),
                        ("a", 1, "La Commission devrait réduire les délais:", "en recrutant des agents"),
                        ("v", 1, "D'ici à fin 2026.")]}
    base.update(kw)
    return base


@pytest.fixture
def fake_source(monkeypatch):
    monkeypatch.setitem(SOURCES, DOC, dict(FAKE))
    return {DOC: TEXT}


# ---------------------------------------------------------------- licence obligatoire
def test_manifest_of_the_pilot_is_valid_and_every_source_has_licence_and_proof():
    assert check_manifest() == []
    for s in SOURCES.values():
        assert s["licence"] and s["preuve_url"].startswith("https://") and s["preuve_extrait"]


@pytest.mark.parametrize("champ", ["licence", "preuve_url", "preuve_extrait", "url"])
def test_manifest_refuses_a_source_without_licence_or_proof(champ):
    bad = {DOC: {**FAKE, champ: ""}}
    assert any(champ in p for p in check_manifest(bad))


def test_manifest_refuses_a_non_free_licence_and_an_http_proof():
    assert check_manifest({DOC: {**FAKE, "licence": "Tous droits réservés"}})
    assert check_manifest({DOC: {**FAKE, "preuve_url": "http://exemple.test/x"}})


def test_build_refuses_to_run_if_a_source_lacks_licence(monkeypatch, fake_source):
    monkeypatch.setitem(SOURCES, DOC, {**FAKE, "licence": ""})
    with pytest.raises(ValueError, match="manifeste invalide"):
        v3_build.build_all(fake_source)


def test_unknown_document_is_refused(tmp_path):
    with pytest.raises(KeyError, match="hors manifeste"):
        source_text(tmp_path, "document-inconnu")


# ---------------------------------------------------------------- rendu identique à l'application
def test_user_prompt_is_exactly_the_application_prompt(fake_source):
    ex = v3_build.build_example(_ex(), fake_source, random.Random(1))
    meta = ex["meta"]
    spec = SectionSpec(**meta["rendu"]["spec"])
    passages = [Passage(label=p["label"], chunk=v3_build._chunk(DOC, "t0", i, p["texte"], p["titre"]),
                        score=1.0, ranks={"bm25": i}) for i, p in enumerate(meta["rendu"]["passages"], 1)]
    assert ex["messages"][1]["content"] == prompting.build_section_prompt(
        spec, passages, nonce=meta["rendu"]["nonce"], lang="fr")
    assert ex["messages"][0]["content"] == prompting.system_prompt("fr")
    assert v3_build.rerender(ex) == ex["messages"][1]["content"]


def test_findings_prompt_is_exactly_the_application_prompt(fake_source):
    ex = v3_build.build_example(
        _ex(id="c0", type="extraction de constats", section=("findings",), phrases=[],
            constats=[(0, "Nous avons constaté que le délai moyen de traitement dépasse un an dans 38 % des dossiers.",
                       "Délais", "medium")]), fake_source, random.Random(2))
    assert ex["meta"]["rendu"]["spec"] is None
    assert v3_build.rerender(ex) == ex["messages"][1]["content"]
    assert ex["messages"][1]["content"].startswith(prompting._t("fr")["task_findings"])
    out = json.loads(ex["messages"][2]["content"])
    assert out["findings"][0]["theme"] == "Délais" and out["findings"][0]["severity"] == "medium"


def test_template_sections_come_from_the_application_templates():
    spec = v3_build.section_spec(("cdc", "perimetre"))
    assert spec.title == "Périmètre" and spec.max_sentences == 8
    assert v3_build.section_spec(("roadmap", "calendrier")).key == "calendrier"
    with pytest.raises(v3_build.CurationError):
        v3_build.section_spec(("cdc", "inexistante"))


# ---------------------------------------------------------------- vérificateur de main
def test_every_example_passes_the_application_verifier(fake_source):
    ex = v3_build.build_example(_ex(), fake_source, random.Random(1))
    assert ex["meta"]["bloquants"] == [] and ex["meta"]["tpv"] == 1.0
    answer = json.loads(ex["messages"][2]["content"])
    assert answer["status"] == "ok" and len(answer["sentences"]) == 3
    kinds = {s["text"][:12]: s["kind"] for s in answer["sentences"]}
    assert kinds["La Commissio"] == "recommendation"


def test_a_sentence_missing_from_the_passage_is_refused(fake_source):
    bad = _ex(phrases=[("v", 0, "Le délai moyen est de trois mois partout.")])
    with pytest.raises(v3_build.CurationError, match="absente"):
        v3_build.build_example(bad, fake_source, random.Random(1))


def test_an_assembled_sentence_needs_both_parts_in_the_passage(fake_source):
    bad = _ex(phrases=[("a", 1, "La Commission devrait réduire les délais:", "en supprimant les contrôles")])
    with pytest.raises(v3_build.CurationError, match="morceau absent"):
        v3_build.build_example(bad, fake_source, random.Random(1))


def test_nuances_are_kept_verbatim(fake_source):
    ex = v3_build.build_example(_ex(phrases=[("v", 0, "Cependant, le service a progressé depuis 2020.")]),
                                fake_source, random.Random(1))
    assert "Cependant, le service a progressé depuis 2020." in ex["messages"][2]["content"]


def test_assemble_only_joins_and_optionally_adds_a_comma():
    assert v3_build.assemble("La Commission devrait:", "agir ;") == "La Commission devrait agir."
    assert v3_build.assemble("La Commission devrait", "lorsque c'est utile, agir", ", ") == \
        "La Commission devrait, lorsque c'est utile, agir."


# ---------------------------------------------------------------- séparation par document
def test_split_is_by_source_document(monkeypatch, fake_source):
    monkeypatch.setitem(SOURCES, "autre", {**FAKE, "id": "autre", "test": True})
    a = v3_build.build_example(_ex(id="a"), fake_source, random.Random(1))
    b = v3_build.build_example(_ex(id="b", doc="autre", passages=[
        v3_curation.P("autre", "Nous avons constaté", "depuis 2020.")], phrases=[
        ("v", 0, "Cependant, le service a progressé depuis 2020.")]), {"autre": TEXT}, random.Random(1))
    assert (a["meta"]["split"], b["meta"]["split"]) == ("train", "test")
    assert v3_build.check_split([a, b]) == []
    b["meta"]["source"], b["meta"]["split"] = DOC, "test"
    assert v3_build.check_split([a, b]) == [DOC]


def test_curation_covers_five_examples_per_type_with_known_documents():
    ex = v3_curation.EXAMPLES
    assert Counter(e["type"] for e in ex) == {t: 5 for t in v3_build.TYPES}
    assert len({e["id"] for e in ex}) == len(ex)
    assert {e["doc"] for e in ex} <= set(SOURCES)
    assert {p["doc"] for e in ex for p in e["passages"]} <= set(SOURCES)
    by_split = Counter(SOURCES[e["doc"]]["test"] for e in ex)
    assert by_split[True] >= 3 and by_split[False] >= 15


def test_each_document_is_only_on_one_side():
    sides = {}
    for e in v3_curation.EXAMPLES:
        sides.setdefault(e["doc"], set()).add(SOURCES[e["doc"]]["test"])
    assert all(len(v) == 1 for v in sides.values())


# ---------------------------------------------------------------- texte, pas de chemin en dur
def test_normalize_joins_lines_and_drops_page_numbers_and_point_numbers():
    raw = "77 La Commission a fait\n\ndes contrôles.\n  52\n\n- une puce\n- autre puce\n"
    assert v3_text.normalize(raw) == "La Commission a fait des contrôles.\nune puce\nautre puce"


def test_between_ignores_line_breaks_and_apostrophe_style():
    t = "Le texte\ncommence ici avec l’apostrophe et finit\nlà. Suite."
    assert v3_text.between(t, "commence ici avec l'apostrophe", "finit là.", include_end=True) == \
        "commence ici avec l’apostrophe et finit là."
    with pytest.raises(ValueError):
        v3_text.between(t, "absent")


def test_between_after_targets_the_right_occurrence():
    t = "Sommaire Titre 5\n\nCorps Titre suite du corps."
    assert v3_text.between(t, "Titre", None, after="Corps").startswith("Titre suite")


def test_no_hardcoded_path_in_the_dataset_scripts():
    root = Path(v3_build.__file__).parent
    for f in root.glob("v3_*.py"):
        code = f.read_text("utf-8")
        assert not re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/|\\\\Users", code), f.name


# ---------------------------------------------------------------- jeu produit (si présent)
OUT = Path(__file__).resolve().parents[1] / "data" / "pilote-v3" / "pilote-25.jsonl"


@pytest.mark.skipif(not OUT.exists(), reason="pilote v3 non produit")
def test_produced_file_rerenders_identically_and_has_licences():
    rows = [json.loads(line) for line in OUT.read_text("utf-8").splitlines()]
    assert len(rows) == 25
    for r in rows:
        assert r["meta"]["licence"] and r["meta"]["licence_preuve"].startswith("https://")
        assert v3_build.rerender(r) == r["messages"][1]["content"]
        assert r["meta"]["bloquants"] == [] and r["meta"]["tpv"] == 1.0
        assert r["meta"]["valide_par_humain"] is False
    assert not {r["meta"]["source"] for r in rows if r["meta"]["split"] == "train"} & \
        {r["meta"]["source"] for r in rows if r["meta"]["split"] == "test"}


def test_a_section_the_application_renders_without_model_is_refused():
    # tor/profil exige des décisions humaines : l'application ne l'envoie pas au modèle (gabarits par type)
    with pytest.raises(v3_build.CurationError, match="exige des décisions"):
        v3_build.section_spec(("tor", "profil"))
    assert all(v3_build.section_spec(e["section"]) for e in v3_curation.EXAMPLES if e["section"][0] != "findings")


def test_v2_example_on_a_decision_section_is_skipped_not_rendered():
    from training.dataset import v2_rerender

    with pytest.raises(v2_rerender.Skipped):
        v2_rerender.template_section_by_title("Profil des experts")
    assert v2_rerender.template_section_by_title("Contraintes")[0] == "gabarit:cdc/contraintes"
