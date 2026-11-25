"""Feuille de route par axes : doublons, lots, noms d'axes, et parcours complet avec un faux modèle."""

import re

from app.domain.generation import Finding
from app.llm import FakeProvider
from app.roadmap import axes
from app.services import roadmap_service
from tests.services.test_generation import USER, _setup


def _f(i, text, theme="t", sev="high", src=None):
    return Finding(id=f"fnd_{i}", dossier_id="d", text=text, theme=theme, severity=sev,
                   source_ids=src or [], validated=True)


def test_dedupe_garde_un_representant_et_ne_perd_rien():
    fs = [_f(1, "La Commission ne rend pas compte systématiquement de son recours aux consultants."),
          _f(2, "La Commission ne rend pas compte systématiquement de son recours aux consultants externes."),
          _f(3, "Les analyses de besoins ne sont pas documentées.")]
    reps, dups = axes.dedupe(fs)
    assert [r.id for r in reps] == ["fnd_1", "fnd_3"]
    assert dups == {"fnd_1": ["fnd_2"], "fnd_3": []}


def test_lots_qui_tiennent_et_element_trop_gros_seul():
    assert axes.batches([3, 3, 3, 9, 1], lambda x: x, 6) == [[3, 3], [3], [9], [1]]


def test_noms_d_axes_fusionnes_sans_casse_ni_accents():
    book = axes.AxisBook()
    book.assign("a", "Gouvernance")
    book.assign("b", "axe : GOUVERNANCE")
    book.assign("c", "Systèmes d'information")
    book.assign("d", "systemes d information")
    book.assign("a", "Autre chose")  # le premier axe donné l'emporte
    assert book.names == ["Gouvernance", "Systèmes d'information"]
    assert book.of == {"a": "Gouvernance", "b": "Gouvernance", "c": "Systèmes d'information",
                       "d": "Systèmes d'information"}
    groups = axes.AxisBook().groups([_f(1, "x")])
    assert groups[0][0] == axes.UNCLASSIFIED


FIN = ["budget", "paie", "achats", "marchés", "contrats", "stocks"]
INFO = ["sécurité", "réseau", "serveurs", "logiciels", "sauvegardes", "messagerie"]


class SensProvider(FakeProvider):
    """Vecteurs « de sens » maîtrisés : finances -> (1, 0), informatique -> (0, 1)."""

    def embed(self, texts):
        out = []
        for k, t in enumerate(texts):
            low = t.lower()
            fin = any(w in low for w in FIN + ["finances"])
            out.append([1.0, 0.0, 0.01 * k] if fin else [0.0, 1.0, 0.01 * k])
        return out


def _handler(prompt, schema):
    """Nom d'axe d'après le contenu ; initiatives : une par axe, + un titre commun à tous les axes."""
    labels = re.findall(r"^F(\d+):", prompt, re.MULTILINE)
    if schema.__name__ == "LLMAxisName":
        body = prompt.split("CONSTATS VALIDÉS :")[1]
        return {"name": "Finances" if any(w in body for w in FIN) else "Systèmes d'information"}
    if schema.__name__ == "LLMInitiatives":
        axis = re.search(r"AXE DE LA FEUILLE DE ROUTE : (.+?) \(", prompt).group(1)
        sc = [{"key": k, "value": 3, "sources": [], "rationale": "r"}
              for k in ("impact", "urgence", "faisabilite", "cout", "risque")]
        return {"initiatives": [
            {"title": f"Renforcer {axis}", "description": "d", "findings": [f"F{n}" for n in labels],
             "scores": sc},
            {"title": "Piloter le programme", "description": "d", "findings": ["F1"], "scores": sc,
             "depends_on_titles": ["Renforcer Finances"]}]}
    return None


def _findings(extra=()):
    fs = [_f(i, f"Le service {w} n'a pas de procédure écrite.", theme=w)
          for i, w in enumerate(FIN + INFO, 1)]
    return fs + list(extra)


def test_beaucoup_de_constats_regroupes_par_le_sens_puis_initiatives_par_axe(repo, tmp_path):
    p = SensProvider(handler=_handler)
    did, _s, _st = _setup(repo, p, tmp_path)
    fs = _findings([_f(99, "Le service budget n'a pas de procédure écrite !")])  # doublon du 1
    repo.save_findings(did, fs)
    r = roadmap_service.generate(repo, p, did, USER)
    items = [it["initiative"] for it in r["roadmap"]["items"]]
    by_title = {i["title"]: i for i in items}
    assert set(by_title) == {"Renforcer Finances", "Renforcer Systèmes d'information", "Piloter le programme"}
    fin_ids = {f.id for f in fs if any(w in f.text for w in FIN)}
    assert set(by_title["Renforcer Finances"]["finding_ids"]) == fin_ids  # doublon compris
    assert by_title["Renforcer Systèmes d'information"]["axis"] == "Systèmes d'information"
    assert {f for i in items for f in i["finding_ids"]} == {f.id for f in fs}  # aucun constat perdu
    assert by_title["Piloter le programme"]["depends_on"] == [by_title["Renforcer Finances"]["id"]]
    kinds = [c["schema"] for c in p.calls if c["kind"] == "structured"]
    assert kinds.count("LLMAxisName") == 2 and kinds.count("LLMInitiatives") == 2
    assert "LLMAxes" not in kinds  # le modèle nomme, le code range


def test_axes_imposes_par_la_fiche_confirmee(repo, tmp_path):
    from app.services import context_sheet

    p = SensProvider(handler=_handler)
    did, _s, _st = _setup(repo, p, tmp_path)
    repo.save_findings(did, _findings())
    context_sheet.save(repo, did, USER, {"roadmap_axes": "Informatique" + chr(10) + "- Finances ; finances"})
    r = roadmap_service.generate(repo, p, did, USER)  # fiche non confirmée : axes ignorés
    assert "LLMAxisName" in [c["schema"] for c in p.calls]
    context_sheet.confirm(repo, did, USER)
    p.calls.clear()
    r = roadmap_service.generate(repo, p, did, USER)
    kinds = [c["schema"] for c in p.calls if c["kind"] == "structured"]
    assert "LLMAxisName" not in kinds  # axes imposés : aucun nom à inventer
    axes_ = {it["initiative"]["axis"] for it in r["roadmap"]["items"]
             if it["initiative"]["title"] != "Piloter le programme"}
    assert axes_ == {"Informatique", "Finances"}


def test_axes_imposes_lus_proprement():
    nl = chr(10)
    text = f"1. Gouvernance{nl}- Sécurité ; sécurité{nl}{nl}• Données"
    assert axes.parse_axes(text) == ["Gouvernance", "Sécurité", "Données"]


def test_regroupement_deterministe_et_nombre_d_axes():
    vecs = [[1, 0], [0.9, 0.1], [0, 1], [0.1, 0.9], [0.95, 0.05]]
    assert axes.cluster(vecs, 2) == [[0, 1, 4], [2, 3]]
    assert [axes.k_for(n) for n in (3, 8, 18, 55, 200)] == [1, 2, 3, 5, 6]


def test_petit_dossier_un_seul_appel_sans_etape_axes(repo, tmp_path):
    p = FakeProvider(handler=_handler)
    did, _s, _st = _setup(repo, p, tmp_path)
    repo.save_findings(did, [_f(1, "Le budget est mal suivi.", theme="Finances"),
                             _f(2, "La paie est manuelle.", theme="Finances")])
    p.handler = lambda prompt, schema: (
        {"initiatives": [{"title": "Fiabiliser", "description": "d", "findings": ["F1", "F2"],
                          "scores": []}]} if schema.__name__ == "LLMInitiatives" else None)
    r = roadmap_service.generate(repo, p, did, USER)
    assert [c["schema"] for c in p.calls if c["kind"] == "structured"] == ["LLMInitiatives"]
    assert r["roadmap"]["items"][0]["initiative"]["axis"] == "Finances"


def test_une_partie_ratee_n_efface_pas_les_autres(repo, tmp_path):
    def handler(prompt, schema):
        if schema.__name__ == "LLMInitiatives" and "AXE DE LA FEUILLE DE ROUTE : Finances" in prompt:
            return "{pas du json"
        return _handler(prompt, schema)

    p = SensProvider(handler=handler)
    did, _s, _st = _setup(repo, p, tmp_path)
    repo.save_findings(did, _findings())
    r = roadmap_service.generate(repo, p, did, USER)
    titles = {it["initiative"]["title"] for it in r["roadmap"]["items"]}
    assert "Renforcer Systèmes d'information" in titles and "Renforcer Finances" not in titles
    assert any("Partie non générée" in w for w in r["warnings"])


def test_tdr_d_une_initiative_ne_recoit_que_ses_constats(repo, tmp_path):
    from app.services import generation

    p = SensProvider(handler=_handler)
    did, search, st = _setup(repo, p, tmp_path)
    fs = _findings()
    repo.save_findings(did, fs)
    r = roadmap_service.generate(repo, p, did, USER)
    ini = next(it["initiative"] for it in r["roadmap"]["items"]
               if it["initiative"]["title"] == "Renforcer Systèmes d'information")
    tor = generation.create_deliverable(repo, did, "tor", USER, initiative_id=ini["id"])
    p.handler = None
    n = len(p.calls)
    generation.generate_section(repo, p, search, tor, "contexte", USER, settings=st)
    prompts = [c["prompt"] for c in p.calls[n:] if c["kind"] == "structured"]
    assert prompts, "la section aurait dû appeler le modèle"
    assert all(f"service {w} " in prompts[0] for w in INFO)
    assert not any(f"service {w} " in prompts[0] for w in FIN)


def test_regroupement_equilibre_quand_tout_se_ressemble():
    # 12 vecteurs proches d'une même direction commune, en 3 familles : le centrage les sépare
    base = [5.0, 5.0, 5.0, 0.0, 0.0, 0.0]
    fams = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    vecs = [base[:3] + [f * (1 + 0.05 * i) for f in fams[i % 3]] for i in range(12)]
    groups = axes.cluster_balanced(vecs, 3)
    assert sorted(len(g) for g in groups) == [4, 4, 4]
    assert all(len({i % 3 for i in g}) == 1 for g in groups)


def test_titre_qui_recopie_la_consigne_est_ecarte():
    assert roadmap_service._echo("Proposer des initiatives qui traitent les constats (cite F1..Fn dans « findings »)")
    assert not roadmap_service._echo("Mettre en place un suivi des fournisseurs")


def test_partie_trop_grosse_coupee_en_deux_et_reprise(repo, tmp_path):
    def handler(prompt, schema):
        if schema.__name__ == "LLMInitiatives" and len(re.findall(r"^F\d+:", prompt, re.MULTILINE)) > 3:
            return "{tronqué"  # réponse coupée, comme en réel quand la partie est trop grosse
        return _handler(prompt, schema)

    p = SensProvider(handler=handler)
    did, _s, _st = _setup(repo, p, tmp_path)
    fs = _findings()
    repo.save_findings(did, fs)
    r = roadmap_service.generate(repo, p, did, USER)
    covered = {f for it in r["roadmap"]["items"] for f in it["initiative"]["finding_ids"]}
    assert covered == {f.id for f in fs}  # tout est repris après découpage
    assert not any("Partie non générée" in w for w in r["warnings"])
