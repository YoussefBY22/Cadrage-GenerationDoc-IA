"""Lot REF : les gabarits portent leurs référentiels et les prompts les citent (sans en faire des sources)."""

import pytest

from app.domain.documents import Chunk
from app.domain.retrieval import Passage
from app.domain.roadmap import Criterion
from app.generation.llm_schemas import LLMInitiative
from app.generation.prompting import build_initiatives_prompt, build_section_prompt
from app.generation.template_loader import load_template

NONCE = "a91f00112233beef"
TYPES = ["findings", "roadmap", "tor", "cdc"]


def passage(n: int, text: str) -> Passage:
    chunk = Chunk(id=f"chk_{n:012d}", document_id="doc_1", dossier_id="dos_1", ordinal=n, text=text,
                  page_start=None, page_end=None, section_path=(), token_estimate=10)
    return Passage(label=f"P{n}", chunk=chunk, score=1.0, ranks={})


@pytest.mark.parametrize("lang", ["fr", "en"])
@pytest.mark.parametrize("type_", TYPES)
def test_chaque_gabarit_et_section_porte_ses_referentiels(type_, lang):
    tpl = load_template(type_, lang)
    assert tpl.referentiels
    for s in tpl.sections:
        assert s.referentiels, f"{type_}/{lang}/{s.key} sans référentiel"
        assert all(len(r) < 160 for r in s.referentiels)  # références courtes, pas de texte recopié


@pytest.mark.parametrize("type_", TYPES)
def test_referentiels_alignes_fr_en(type_):
    fr, en = load_template(type_, "fr"), load_template(type_, "en")
    assert [len(s.referentiels) for s in fr.sections] == [len(s.referentiels) for s in en.sections]


def test_cdc_suit_29148_et_tor_banque_mondiale_ue():
    assert "29148" in " ".join(load_template("cdc").referentiels)
    tor = " ".join(load_template("tor").referentiels)
    assert "Banque mondiale" in tor and "PM²" in tor
    assert "31000" in " ".join(load_template("roadmap").sections[-1].referentiels)
    fonc = next(s for s in load_template("cdc").sections if s.key == "fonctionnelles")
    assert "REQ-1" in fonc.instructions and "vérifiable" in fonc.instructions


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_prompt_de_section_contient_les_referentiels_comme_cadre(lang):
    spec = load_template("cdc", lang).sections[1]
    prompt = build_section_prompt(spec, [passage(1, "Le système permet la saisie.")], nonce=NONCE, lang=lang)
    for r in spec.referentiels:
        assert r in prompt
    assert prompt.index("29148") > prompt.index("<<FIN")  # après les passages, avec la consigne
    assert ("jamais une source" in prompt) or ("never a source" in prompt)


def test_prompt_sans_referentiel_inchange():
    spec = load_template("cdc").sections[0].model_copy(update={"referentiels": []})
    prompt = build_section_prompt(spec, [passage(1, "Texte.")], nonce=NONCE)
    assert "RÉFÉRENTIELS" not in prompt


def test_prompt_initiatives_propose_etiquette_domaine():
    crit = [Criterion(key="impact", label="Impact", weight=1.0)]
    for lang, word in (("fr", "COBIT"), ("en", "COBIT")):
        p = build_initiatives_prompt([], [passage(1, "Texte.")], crit, nonce=NONCE, lang=lang)
        assert word in p and "domain" in p


def test_schema_llm_domaine_facultatif():
    ini = LLMInitiative(title="t", description="d", findings=["F1"], scores=[])
    assert ini.domain is None
