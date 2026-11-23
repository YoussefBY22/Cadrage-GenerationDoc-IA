"""Lot B, bloc 3 : gabarits par type de projet (FR-24) — tronc commun + modules combinables."""

import pytest

from app.domain.context import PROJECT_TYPES
from app.generation.template_loader import (
    TemplateError,
    available_modules,
    load_template,
    template_for,
)
from app.llm import FakeProvider
from app.services import decisions as dec
from app.services import generation
from app.workflow import versions as vs
from tests.services.test_generation import USER, _setup
from tests.services.test_generation_fakes import honest

V1 = "/api/v1"


def test_les_huit_modules_existent_dans_les_deux_langues():
    assert available_modules() == list(PROJECT_TYPES)
    for typ in ("tor", "cdc"):
        for lang in ("fr", "en"):
            trunk = load_template(typ, lang)
            for m in PROJECT_TYPES:
                tpl = load_template(typ, lang, [m])
                keys = [s.key for s in tpl.sections]
                assert len(keys) == len(set(keys))
                assert {s.key for s in trunk.sections} <= set(keys)  # le tronc reste entier
                assert all(len(s.queries) >= 2 for s in tpl.sections)


def test_fr_et_en_ont_les_memes_sections():
    for typ in ("tor", "cdc"):
        for m in PROJECT_TYPES:
            fr = [s.key for s in load_template(typ, "fr", [m]).sections]
            en = [s.key for s in load_template(typ, "en", [m]).sections]
            assert fr == en


def test_combinaison_ordre_canonique_et_tronc_conserve():
    a = load_template("cdc", "fr", ["training", "software"])
    b = load_template("cdc", "fr", ["software", "training", "software"])
    assert [s.key for s in a.sections] == [s.key for s in b.sections]
    keys = [s.key for s in a.sections]
    assert keys.index("sw_integration") < keys.index("frm_public")  # ordre des types de projet
    assert keys.index("non_fonctionnelles") < keys.index("sw_integration") < keys.index("contraintes")
    assert keys[-1] == "recette"
    trunk = load_template("cdc", "fr")
    assert all(s.referentiels == t.referentiels or set(t.referentiels) <= set(s.referentiels)
               for s, t in zip([x for x in a.sections if x.key in {y.key for y in trunk.sections}],
                               trunk.sections, strict=True))  # les référentiels du tronc restent


def test_module_adapte_une_section_du_tronc_sans_rien_retirer():
    trunk = {s.key: s for s in load_template("cdc", "fr").sections}
    soft = {s.key: s for s in load_template("cdc", "fr", ["software"]).sections}
    assert "tests de charge" in soft["recette"].instructions
    assert soft["recette"].instructions.startswith(trunk["recette"].instructions)
    assert set(trunk["recette"].referentiels) < set(soft["recette"].referentiels)
    assert set(trunk["recette"].queries) < set(soft["recette"].queries)


def test_chaque_module_declare_les_decisions_qu_il_exige():
    for m in PROJECT_TYPES:
        tpl = load_template("cdc", "fr", [m])
        added = [s for s in tpl.sections if s.key.split("_")[0] in {"sw", "da", "inf", "sup", "srv",
                                                                   "etu", "chg", "frm"}]
        assert added and any(s.requires_decisions for s in added), m


def test_module_inconnu_refuse():
    with pytest.raises(TemplateError):
        load_template("tor", "fr", ["magie"])


# --- parcours : trois types de projet générés section par section ---------------------------------
def _setup_dossier(repo, tmp_path):
    p = FakeProvider(handler=honest)
    did, search, st = _setup(repo, p, tmp_path)
    return p, did, search, st


@pytest.mark.parametrize("modules", [["software"], ["training"], ["infrastructure"]])
@pytest.mark.parametrize("typ", ["tor", "cdc"])
def test_trois_types_de_projet_generes_section_par_section(repo, tmp_path, modules, typ):
    p, did, search, st = _setup_dossier(repo, tmp_path)
    dl = generation.create_deliverable(repo, did, typ, USER, modules=modules)
    _, content = repo.get_version(dl)
    assert content.modules == modules
    tpl = template_for(content)
    needed = {c for s in tpl.sections for c in s.requires_decisions}
    for cat in sorted(needed):
        dec.confirm(repo, dec.create(repo, did, USER, category=cat, text=f"Décision {cat} retenue."),
                    USER)
    for spec in tpl.sections:
        r = generation.generate_section(repo, p, search, dl, spec.key, USER, settings=st)
        assert r["status"] == "ok", (spec.key, r["section"]["missing_evidence"])
        assert r["tpv"] == 1.0, (spec.key, r["report"]["issues"])
    _, content = repo.get_version(dl)
    assert [d.section_key for d in content.sections] == [s.key for s in tpl.sections]
    assert any(s.key.split("_")[0] in {"sw", "frm", "inf"} for s in tpl.sections)


def test_section_de_module_sans_decision_refusee_sans_appel(repo, tmp_path):
    p, did, search, st = _setup_dossier(repo, tmp_path)
    dl = generation.create_deliverable(repo, did, "cdc", USER, modules=["data_ai"])
    r = generation.generate_section(repo, p, search, dl, "da_modele", USER, settings=st)
    assert r["status"] == "refused" and p.calls == []
    assert r["section"]["missing_evidence"] == "décision humaine requise : critère d'évaluation"


def test_modules_par_defaut_viennent_de_la_fiche_confirmee(repo, tmp_path):
    from app.services import context_sheet

    _p, did, _search, _st = _setup_dossier(repo, tmp_path)
    context_sheet.save(repo, did, USER, {"project_types": ["training"]})
    assert _modules(repo, did) == []  # fiche brouillon : ignorée
    context_sheet.confirm(repo, did, USER)
    assert _modules(repo, did) == ["training"]
    dl = generation.create_deliverable(repo, did, "tor", USER, modules=[])  # [] = tronc seul
    assert repo.get_version(dl)[1].modules == []


def _modules(repo, did):
    dl = generation.create_deliverable(repo, did, "cdc", USER)
    return repo.get_version(dl)[1].modules


def test_circuit_d_approbation_exige_les_sections_du_module(repo, tmp_path):
    """Le verrou existant s'applique aux sections ajoutées : un module non rédigé bloque l'approbation."""
    from app.api.routes_workflow import _approval_facts

    p, did, search, st = _setup_dossier(repo, tmp_path)
    dl = generation.create_deliverable(repo, did, "cdc", USER, modules=["software"])
    row = vs.get_deliverable(repo, dl)
    _, content = repo.get_version(dl)
    for spec in load_template("cdc", "fr").sections:  # tronc seulement rédigé
        generation.generate_section(repo, p, search, dl, spec.key, USER, settings=st)
    version, content = repo.get_version(dl)
    _failures, complete, _ = _approval_facts(repo, row, version, content)
    assert complete is False


# --- API -----------------------------------------------------------------------------------------
def test_api_apercu_et_creation_avec_modules(client):
    did = client.post(f"{V1}/dossiers", json={"name": "D", "client_name": "C"}).json()["id"]
    mods = client.get(f"{V1}/templates/modules").json()
    assert [m["id"] for m in mods] == list(PROJECT_TYPES) and mods[0]["label"] == "Logiciel et SI"
    prev = client.get(f"{V1}/templates/tor", params={"modules": ["training"]}).json()
    keys = {s["key"]: s for s in prev["sections"]}
    assert keys["profil"]["requires_labels"] == ["profil"]
    assert keys["frm_formateurs"]["requires_decisions"] == ["profile"]
    assert client.get(f"{V1}/templates/tor", params={"modules": ["magie"]}).status_code == 422
    r = client.post(f"{V1}/dossiers/{did}/deliverables", json={"type": "cdc", "modules": ["software"]})
    d = client.get(f"{V1}/deliverables/{r.json()['deliverable_id']}").json()
    assert d["modules"] == ["software"]
    assert {"sw_integration", "recette"} <= {s["key"] for s in d["sections"]}
    bad = client.post(f"{V1}/dossiers/{did}/deliverables", json={"type": "cdc", "modules": ["magie"]})
    assert bad.status_code == 422


def test_les_modules_d_un_livrable_ne_changent_pas_a_l_edition(client):
    did = client.post(f"{V1}/dossiers", json={"name": "D", "client_name": "C"}).json()["id"]
    dl = client.post(f"{V1}/dossiers/{did}/deliverables",
                     json={"type": "cdc", "modules": ["software"]}).json()["deliverable_id"]
    content = client.get(f"{V1}/deliverables/{dl}").json()["content"]
    assert client.put(f"{V1}/deliverables/{dl}/content", json=content).status_code == 200
    content["modules"] = []
    r = client.put(f"{V1}/deliverables/{dl}/content", json=content)
    assert r.status_code == 422 and r.json()["error"]["code"] == "IDENTITY_CHANGED"
