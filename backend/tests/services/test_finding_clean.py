"""Lot 3 : constats propres (bruit écarté, doublons fusionnés réversibles, reformulation sûre) et
recommandations complètes (sous-points, échéance, paragraphes cités)."""

from app.services import finding_clean as fc
from app.services.reco_details import assemble, finding_links, numbers, parse

RAPPORT = [
    ("c1", 40, 40, ("86 Nous avons relevé d'importantes lacunes dans le cadre (points 18 à 26).\n"
                   "87 La Commission a fait appel à des consultants (points 24 et 28 à 32).")),
    ("c2", 42, 42, ("Recommandation n° 1 – Compléter le cadre en place régissant le recours aux consultants\n"
                   "La Commission devrait continuer à développer son cadre. Ce cadre devrait:\n"
                   "a) définir les formes de soutien;\nb) comporter des orientations; 43\n"
                   "Quand? D'ici à décembre 2023.\n"
                   "88 Nous avons constaté que la Commission avait respecté le règlement (points 34 à 36).")),
    ("c3", 43, 43, ("Recommandation n° 2 – Améliorer la surveillance des risques\n"
                   "La Commission devrait analyser les risques.\nQuand? D'ici à juin 2024.")),
]


def test_recommandation_complete():
    full, spans = assemble(RAPPORT)
    d = parse(full, spans)
    r1 = d[1]
    assert r1["title"].startswith("Compléter le cadre")
    assert r1["intro"].startswith("La Commission devrait")
    assert [x["label"] for x in r1["sub_points"]] == ["a", "b"]
    assert r1["sub_points"][1]["text"] == "comporter des orientations"  # numéro de page retiré
    assert r1["deadline"] == "D'ici à décembre 2023"
    assert r1["points"] == [18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30, 31, 32]
    assert d[2]["points"] == [34, 35, 36] and d[2]["deadline"] == "D'ici à juin 2024"


def test_numeros_de_points():
    assert numbers("24 et 28 à 32") == [24, 28, 29, 30, 31, 32]
    assert numbers("4, 7 and 9-11") == [4, 7, 9, 10, 11]


def test_constat_relie_a_sa_recommandation():
    full, _ = assemble([("c", 1, 1, "17 Contexte.\n\n20 La Commission ne documentait pas ses besoins.")])
    links = finding_links(full, {"f": "La Commission ne documentait pas ses besoins."},
                          [{"id": "R1", "points": [18, 19, 20]}])
    assert links["f"]["paragraph"] == 20 and links["f"]["recommendation_ids"] == ["R1"]


def test_bruit_et_reformulation_par_regle():
    assert fc.noise_reason("Nous avons examiné si la Commission avait mis en place un cadre approprié.")
    assert fc.noise_reason("La figure 6 présente une ventilation des montants contractuels.")
    assert fc.noise_reason("La figure 8 montre que certaines directions générales dépendent de peu de contractants.") is None
    assert fc.rule_rewrite("Nous avons constaté que les DG ne documentaient pas leurs besoins.") == \
        "Il a été constaté que les DG ne documentaient pas leurs besoins."
    assert fc.rule_rewrite("Cela étant, certains prestataires gagnent souvent.") == \
        "Il a été constaté que certains prestataires gagnent souvent."


def test_garde_fou_chiffres():
    assert fc._numbers("22 % de 600,1 millions") == {"22", "600,1"}


def test_regle_ou_condition_n_est_pas_un_manque():
    assert fc.kind_check("probleme", "Si elles considèrent ces risques critiques, elles sont censées les signaler.")[0] == "contexte"
    assert fc.kind_check("probleme", "Nous avons constaté que les DG ne documentaient pas leurs besoins.")[0] == "probleme"
    assert fc.kind_check("probleme", "Cette concentration crée un risque de dépendance excessive.")[0] == "probleme"


def test_numero_de_page_n_est_pas_un_paragraphe():
    from app.services.reco_details import paragraph_at
    texte = "2\n\nSynthèse\nI Chaque année\n\n30 Lorsque les DG"
    assert paragraph_at(texte, 5) is None and paragraph_at(texte, 40) == 30


def test_regle_simple_corrigee_et_fusion_prudente():
    assert fc.rule_rewrite("Par conséquent, nous avons observé un risque de dépendance.") == \
        "Il a été observé un risque de dépendance."
    assert fc.rule_rewrite("11 Au sein de la structure, les DG décident.") == "Il a été constaté qu'au sein de la structure, les DG décident."
    assert "locaux." in fc.rule_rewrite("Les contractants travaillant dans ses locaux14. Elle précise.")
    assert not fc.same_finding(
        "Les lignes directrices donnaient des orientations pour le suivi et l'analyse de la contribution des travaux.",
        "Les lignes directrices donnaient des orientations concernant la planification et la justification du recours.")
    assert fc.same_finding("Seules certaines directions générales procédaient à des évaluations ex post une fois les contrats achevés.",
                           "Seules certaines directions générales procédaient à des évaluations ex post une fois les contrats conclus.")
