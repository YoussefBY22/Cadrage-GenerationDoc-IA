"""Tâche « axes » : vérité tirée du sommaire, invite de l'application, réponse au format du schéma."""

import json
import random

from training.dataset import eca_axes, schema_order, v3_build

TOC_2022 = """Table des matières
                                                                       Points
Observations                                                                   18 - 84
Importantes lacunes dans le cadre régissant l'engagement de
consultants externes et la justification du recours aux services de
ces derniers                                                                   18 - 32
Les lignes directrices pour une meilleure réglementation: une base solide,     20 - 26
qui ne s'applique toutefois qu'aux évaluations et aux études
Les procédures de passation de marchés ont été respectées, mais
la gestion des risques spécifiques laisse encore à désirer                     33 - 56
La supervision effectuée par la Commission ne correspondait pas au niveau
de risque potentiel                                                            37 - 56
Manque de précision dans les informations de gestion de la                  72 - 84
Commission et absence de compte rendu systématique
Manquements dans la manière dont les services des consultants
externes sont gérés et utilisés                                                57 - 71
Conclusions et recommandations                                              85 - 91
"""

TOC_2025 = """Table des matières
Points
01 - 19 | Principaux messages
20 - 78 | Nos observations en détail
  20 - 46 | La gestion à distance permet l'acheminement de l'aide
              humanitaire, mais elle pourrait être mieux conçue
    21 - 26 | La gestion à distance joue un rôle primordial
  47 - 62 | La certification des ONG partenaires réduit les risques
  63 - 78 | La présence sur le terrain renforce la surveillance
79 - 90 | Conclusions et recommandations
"""


def test_sommaire_2022_grandes_parties_seulement():
    axes = eca_axes.toc_axes(TOC_2022)
    assert [(a.first, a.last) for a in axes] == [(18, 32), (33, 56), (57, 71), (72, 84)]
    assert axes[0].title.startswith("Importantes lacunes") and axes[0].title.endswith("ces derniers")
    assert axes[3].title.endswith("compte rendu systématique")
    assert eca_axes.axis_of(40, axes).first == 33


def test_sommaire_2025_avec_barres():
    axes = eca_axes.toc_axes(TOC_2025)
    assert [(a.first, a.last) for a in axes] == [(20, 46), (47, 62), (63, 78)]
    assert axes[0].title.endswith("mieux conçue")


def test_sommaire_illisible_ou_trou_renvoie_rien():
    assert eca_axes.toc_axes("Pas de sommaire ici") == []
    trou = TOC_2022.replace("57 - 71", "60 - 71")  # points 57-59 sans partie : on ne s'y fie pas
    assert eca_axes.toc_axes(trou) == []


def _report():
    subjects_a = ["règles communes", "analyses de besoins", "choix des consultants", "listes d'activités",
                  "formes de soutien", "méthodes communes"]
    subjects_b = ["risques de dépendance", "risques de concentration", "conflits d'intérêts",
                  "avantages concurrentiels", "contrôles centraux", "registres des risques"]
    filler = " Cette situation a été observée dans plusieurs services et sur la période examinée par la Cour."
    paras = [f"{18 + i} La Commission n'a pas encadré les {w} des directions générales en 2021.{filler * 2}"
             for i, w in enumerate(subjects_a)]
    paras += [f"{24 + i} Nous avons constaté que les {w} ne sont pas évalués à l'échelle de l'institution.{filler * 2}"
              for i, w in enumerate(subjects_b)]
    toc = """Table des matières
Observations                                                    18 - 29
Le cadre présente des lacunes                                   18 - 23
La gestion des risques laisse à désirer                         24 - 29
Conclusions et recommandations                                  30 - 35
"""
    sep = chr(10) * 2
    return {"id": "eca-sr-2099-01", "url": "https://example.test/sr", "text": toc + sep + sep.join(paras)}


def test_exemples_justes_invite_reproduite_et_ordre_du_schema():
    rep = _report()
    exs = eca_axes.build_examples(rep, random.Random(1))
    assert exs
    for ex in exs:
        assert eca_axes.check(ex, rep["text"]) == []
        assert v3_build.rerender(ex) == ex["messages"][1]["content"]
        ans = json.loads(ex["messages"][2]["content"])
        assert schema_order.is_ordered(eca_axes.schema_for(len(ans["assignments"])), ans)
        names = eca_axes.names_of(ex)
        for c, name in zip(ex["meta"]["rendu"]["constats"], names, strict=True):
            expected = "Le cadre présente des lacunes" if c["point"] <= 23 else "La gestion des risques laisse à désirer"
            assert name == expected
    suivant = next(e for e in exs if e["meta"]["rendu"]["axes_connus"])
    assert json.loads(suivant["messages"][2]["content"])["new_axes"] == []
    assert "A1: Le cadre présente des lacunes" in suivant["messages"][1]["content"]


def test_un_mauvais_axe_est_refuse():
    rep = _report()
    ex = eca_axes.build_examples(rep, random.Random(1))[0]
    ans = json.loads(ex["messages"][2]["content"])
    ans["assignments"][0]["axis"] = "A9"
    ex["messages"][2]["content"] = json.dumps(ans, ensure_ascii=False)
    assert eca_axes.check(ex, rep["text"])
