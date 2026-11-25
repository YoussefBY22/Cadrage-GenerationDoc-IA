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


def _handler(prompt, schema):
    """Axes : F impairs → Gouvernance, F pairs → Données. Initiatives : une par axe, + un titre commun."""
    labels = re.findall(r"^F(\d+):", prompt, re.MULTILINE)
    if schema.__name__ == "LLMAxes":
        known = re.findall(r"^A(\d+): (.+)$", prompt, re.MULTILINE)
        ids = {name: f"A{k}" for k, name in known}
        new_axes = [{"id": f"A{len(ids) + 1 + j}", "name": nm}
                    for j, nm in enumerate(x for x in ("Gouvernance", "données") if x not in ids)]
        ids |= {a["name"]: a["id"] for a in new_axes}
        return {"new_axes": new_axes,
                "assignments": [{"finding": f"F{n}", "axis": ids["Gouvernance" if int(n) % 2 else "données"]}
                                for n in labels]}
    if schema.__name__ == "LLMInitiatives":
        axis = re.search(r"AXE DE LA FEUILLE DE ROUTE : (.+?) \(", prompt).group(1)
        sc = [{"key": k, "value": 3, "sources": [], "rationale": "r"}
              for k in ("impact", "urgence", "effort", "risque")]
        return {"initiatives": [
            {"title": f"Renforcer {axis}", "description": "d", "findings": [f"F{n}" for n in labels],
             "scores": sc},
            {"title": "Piloter le programme", "description": "d", "findings": ["F1"], "scores": sc,
             "depends_on_titles": ["Renforcer Gouvernance"]}]}
    return None


def test_beaucoup_de_constats_axes_puis_initiatives_par_axe(repo, tmp_path):
    p = FakeProvider(handler=_handler)
    did, _s, _st = _setup(repo, p, tmp_path)
    chunk = next(iter(repo.get_chunks(did, [c.id for c in repo.list_chunks(did)]).values())) \
        if hasattr(repo, "list_chunks") else None
    src = [chunk.id] if chunk else []
    subjects = ["budget", "paie", "archives", "achats", "marchés", "formation", "sécurité", "réseau",
                "courrier", "contrats", "stocks", "véhicules"]
    fs = [_f(i, f"Le service {s} n'a pas de procédure écrite numéro {i}.", theme=s, src=src)
          for i, s in enumerate(subjects, 1)]
    fs.append(_f(99, "Le service budget n'a pas de procédure écrite numéro 1.", src=src))  # doublon de 1
    repo.save_findings(did, fs)
    r = roadmap_service.generate(repo, p, did, USER)
    items = [it["initiative"] for it in r["roadmap"]["items"]]
    by_title = {i["title"]: i for i in items}
    assert set(by_title) == {"Renforcer Gouvernance", "Renforcer Données", "Piloter le programme"}
    assert by_title["Renforcer Gouvernance"]["axis"] == "Gouvernance"
    assert by_title["Renforcer Données"]["axis"] == "Données"
    # même titre proposé dans deux axes : une seule initiative ; le doublon suit son représentant
    assert "fnd_99" in by_title["Renforcer Gouvernance"]["finding_ids"]
    covered = {f for i in items for f in i["finding_ids"]}
    assert covered == {f.id for f in fs}  # aucun constat perdu
    assert by_title["Piloter le programme"]["depends_on"] == [by_title["Renforcer Gouvernance"]["id"]]
    kinds = [c["schema"] for c in p.calls if c["kind"] == "structured"]
    assert kinds.count("LLMAxes") == 1 and kinds.count("LLMInitiatives") == 2


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
        if schema.__name__ == "LLMInitiatives" and "AXE DE LA FEUILLE DE ROUTE : Données" in prompt:
            return "{pas du json"
        return _handler(prompt, schema)

    p = FakeProvider(handler=handler)
    did, _s, _st = _setup(repo, p, tmp_path)
    repo.save_findings(did, [_f(i, f"Constat distinct sur le sujet {w}.", theme=w)
                             for i, w in enumerate(["budget", "paie", "archives", "achats", "marchés",
                                                    "formation", "sécurité", "réseau", "courrier",
                                                    "contrats"], 1)])
    r = roadmap_service.generate(repo, p, did, USER)
    titles = {it["initiative"]["title"] for it in r["roadmap"]["items"]}
    assert "Renforcer Gouvernance" in titles and "Renforcer Données" not in titles
    assert any("Partie non générée" in w for w in r["warnings"])


def test_tdr_d_une_initiative_ne_recoit_que_ses_constats(repo, tmp_path):
    from app.services import generation

    p = FakeProvider(handler=_handler)
    did, search, st = _setup(repo, p, tmp_path)
    words = ["budget", "paie", "archives", "achats", "marchés", "formation", "sécurité", "réseau",
             "courrier", "contrats"]
    repo.save_findings(did, [_f(i, f"Constat distinct sur le sujet {w}.", theme=w)
                             for i, w in enumerate(words, 1)])
    r = roadmap_service.generate(repo, p, did, USER)
    ini = next(it["initiative"] for it in r["roadmap"]["items"]
               if it["initiative"]["title"] == "Renforcer Données")
    tor = generation.create_deliverable(repo, did, "tor", USER, initiative_id=ini["id"])
    p.handler = None
    n = len(p.calls)
    generation.generate_section(repo, p, search, tor, "contexte", USER, settings=st)
    prompts = [c["prompt"] for c in p.calls[n:] if c["kind"] == "structured"]
    assert prompts, "la section aurait dû appeler le modèle"
    mine = {f"sujet {words[int(x[4:]) - 1]}" for x in ini["finding_ids"]}
    others = {f"sujet {w}" for w in words} - mine
    assert all(m in prompts[0] for m in mine) and not any(o in prompts[0] for o in others)


def test_lots_suivants_reutilisent_les_axes_par_identifiant(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(roadmap_service, "AXES_BATCH", 4)
    p = FakeProvider(handler=_handler)
    did, _s, _st = _setup(repo, p, tmp_path)
    words = ["budget", "paie", "archives", "achats", "marchés", "formation", "sécurité", "réseau",
             "courrier", "contrats", "stocks"]
    repo.save_findings(did, [_f(i, f"Constat distinct sur le sujet {w}.", theme=w)
                             for i, w in enumerate(words, 1)])
    r = roadmap_service.generate(repo, p, did, USER)
    axes_prompts = [c["prompt"] for c in p.calls if c.get("schema") == "LLMAxes"]
    assert len(axes_prompts) == 3
    assert "A1: Gouvernance" in axes_prompts[1] and "A2: Données" in axes_prompts[1]
    assert {it["initiative"]["axis"] for it in r["roadmap"]["items"]} == {"Gouvernance", "Données"}
