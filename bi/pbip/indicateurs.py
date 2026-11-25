"""Indicateurs du rapport Power BI : source unique des mesures, de `bi/measures.dax` et de `bi/KPI.md`.

Power BI compte et affiche ; les règles d'action (« que faire ensuite ») sont des seuils explicites, écrits ici
une fois, générés en DAX et documentés dans KPI.md. Aucun modèle de langue n'intervient.
"""
from __future__ import annotations

from dataclasses import dataclass

ANTHRACITE, GRIS, GRIS_CLAIR, JAUNE = "#2E2E38", "#747480", "#C4C4CD", "#FFE600"
GRIS_TEXTE = "#5F5F6B"  # le gris de la charte n'atteint pas 4,5:1 sur le fond (4,28) : réservé aux aplats
ROUGE = "#B4232F"  # alerte : toujours doublé d'un libellé, jamais opposé à un vert
JAUNE_PALE, JAUNE_MOYEN = "#FFF7B3", "#FFEE66"

TOUS, TOUS_MOIS, TOUTES_DONNEES = "Tous", "Tous les mois", "Réelles + démonstration"
PCT, PCT1, ENTIER, SECONDES, PERTE = "0 %", "0.0 %", "#,0", '0.0 "s"', "0.000"
G = "'Générations'"
ETAPES = '{"_findings", "_axes", "_initiatives"}'

# Seuils des règles d'action (que faire ensuite)
SEUIL_NON_VERIFIEES = 0.10   # part de phrases non vérifiées au-delà de laquelle on revoit les sources
SEUIL_REFUS = 0.20           # part de sections refusées au-delà de laquelle on complète les documents
SEUIL_INVALIDES = 0.10       # part d'appels « feuille de route » invalides
MIN_PHRASES_SECTION = 10     # une section n'est désignée qu'avec au moins 10 phrases

ERREURS = [
    ("failed", "Phrase non vérifiée", 1, "Le vérificateur ne retrouve pas la phrase dans la source citée."),
    ("warning", "Phrase à revoir", 2, "Appui faible : la source ne soutient la phrase qu'en partie."),
    ("citation", "Citation sans source", 3, "La source citée n'existe pas dans le dossier."),
    ("invalid", "Sortie invalide", 4, "La réponse du modèle ne respecte pas le format attendu."),
]


@dataclass(frozen=True)
class Mesure:
    nom: str
    dossier: str
    dax: str
    fmt: str | None = None
    description: str = ""
    masquee: bool = False


@dataclass(frozen=True)
class Action:
    rang: int
    nom: str
    condition: str
    pour: str
    texte: str  # expression DAX qui renvoie le texte affiché (sans « | »)
    regle: str  # la règle en français, pour KPI.md


def compte(table: str, *filtres: str, zero: bool = True) -> str:
    """Compte ; `zero=False` pour un graphique : une catégorie vide ne s'affiche pas (pas de barre à 0)."""
    plus = " + 0" if zero else ""
    return f"CALCULATE(COUNTROWS({table}), {', '.join(filtres)}){plus}" if filtres else f"COUNTROWS({table}){plus}"


def _base() -> list[Mesure]:
    a, q, r, e = "1. Activité", "2. Qualité de l'IA", "3. Recommandations des rapports", "4. Entraînement"
    sections = f"FILTER({G}, NOT {G}[Code de section] IN {ETAPES})"
    feuille = f'{G}[Code de section] IN {{"_axes", "_initiatives"}}'
    return [
        Mesure("Projets", a, "COUNTROWS(Projets) + 0", ENTIER, "Projets (dossiers) dans le périmètre des filtres."),
        Mesure("Projets de démonstration", a, compte("Projets", 'Projets[Données] = "Démonstration"'), ENTIER),
        Mesure("Projets réels", a, compte("Projets", 'Projets[Données] = "Réelles"'), ENTIER),
        Mesure("Documents", a, "SUM(Projets[Documents]) + 0", ENTIER),
        Mesure("Livrables", a, "COUNTROWS(Livrables)", ENTIER, "Livrables créés dans la période."),
        Mesure("Brouillons", a, compte("Livrables", 'Livrables[Code d\'état] = "draft"'), ENTIER),
        Mesure("En relecture", a, compte("Livrables", 'Livrables[Code d\'état] = "in_review"'), ENTIER),
        Mesure("Approuvés", a, compte("Livrables", 'Livrables[Code d\'état] = "approved"'), ENTIER),
        Mesure("Renvoyés", a, compte("Livrables", 'Livrables[Code d\'état] = "rejected"'), ENTIER),
        Mesure("Constats", a, "COUNTROWS(Constats)", ENTIER),
        Mesure("Constats à valider", a, compte("Constats", "Constats[Validé] = 0"), ENTIER),
        Mesure("Initiatives", a, "COUNTROWS(Initiatives)", ENTIER),
        Mesure("Constats traités", a, "SUM(Initiatives[Constats traités])", ENTIER),
        Mesure("Appels au modèle", a, f"COUNTROWS({G})", ENTIER,
               "Chaque appel : une section, une extraction de constats, un regroupement en axes, des initiatives."),
        Mesure("Temps moyen par appel", a, f"DIVIDE(AVERAGE({G}[Durée en ms]), 1000)", SECONDES,
               "Durée moyenne d'un appel au modèle, en secondes, sur le PC local."),

        Mesure("Appels en erreur", q, f"SUM({G}[En erreur]) + 0", ENTIER),
        Mesure("Taux d'erreur de l'IA", q, "DIVIDE([Appels en erreur], [Appels au modèle])", PCT,
               "Part des appels avec au moins une erreur : sortie invalide, phrase non vérifiée ou citation sans "
               "source. Un refus faute de preuve est le comportement voulu : il n'est pas compté, voir Taux de refus."),
        Mesure("Phrases générées", q, f"SUM({G}[Phrases produites]) + 0", ENTIER),
        Mesure("Phrases vérifiées", q, f"SUM({G}[Phrases validées]) + 0", ENTIER),
        Mesure("Taux de phrases vérifiées", q, "DIVIDE([Phrases vérifiées], [Phrases générées])", PCT,
               "Phrases retrouvées dans leur source par le vérificateur ÷ phrases générées."),
        Mesure("Phrases non vérifiées", q, f"SUM({G}[Phrases non vérifiées]) + 0", ENTIER),
        Mesure("Taux de phrases non vérifiées", q, "DIVIDE([Phrases non vérifiées], [Phrases générées])", PCT1),
        Mesure("Phrases à revoir", q, f"SUM({G}[Phrases à revoir]) + 0", ENTIER),
        Mesure("Citations générées", q, f"SUM({G}[Citations produites]) + 0", ENTIER),
        Mesure("Citations sans source", q, f"SUM({G}[Citations produites]) - SUM({G}[Citations valides]) + 0", ENTIER),
        Mesure("Taux de citations sans source", q, "DIVIDE([Citations sans source], [Citations générées])", PCT1),
        Mesure("Sections générées", q, f"COUNTROWS({sections}) + 0", ENTIER),
        Mesure("Sections refusées", q, compte(G, f'{G}[Statut] = "refused"'), ENTIER),
        Mesure("Taux de refus", q, "DIVIDE([Sections refusées], [Sections générées])", PCT,
               "Sections où le modèle répond « preuves insuffisantes » ÷ sections demandées."),
        Mesure("Sorties invalides", q, compte(G, f'{G}[Statut] = "invalid"'), ENTIER),
        Mesure("Appels feuille de route", q, compte(G, feuille), ENTIER),
        Mesure("Erreurs", q, "SWITCH(SELECTEDVALUE('Types d''erreur'[Code d'erreur]), "
                             '"failed", [Phrases non vérifiées], "warning", [Phrases à revoir], '
                             '"citation", [Citations sans source], "invalid", [Sorties invalides])', ENTIER, "Erreurs du type choisi (table Types d'erreur)."),

        Mesure("Rapports d'audit", r, "COUNTROWS(Rapports) + 0", ENTIER),
        Mesure("Recommandations annoncées", r, "SUM(Rapports[Annoncées]) + 0", ENTIER,
               "Numéros « Recommandation n° … » que le rapport annonce (plus grand numéro cité)."),
        Mesure("Recommandations retenues", r, compte("Recommandations", "Recommandations[Active] = 1", zero=False), ENTIER,
               "Version corrigée par le consultant : supprimées et fusionnées exclues."),
        Mesure("Recommandations validées", r, compte("Recommandations", 'Recommandations[Code du statut] = "validated"', zero=False), ENTIER),
        Mesure("Recommandations à valider", r, compte("Recommandations", 'Recommandations[Code du statut] = "proposed"', zero=False), ENTIER),
        Mesure("Recommandations manquantes", r, "SUM(Rapports[Manquantes])", ENTIER,
               "Numéros annoncés par le rapport mais absents des recommandations retenues."),
        Mesure("Rapports en alerte", r, "SUM(Rapports[En alerte]) + 0", ENTIER,
               "Rapports avec un écart de numérotation (trou, doublon) ou sans aucune recommandation détectée."),

        Mesure("Entraînements", e, "COUNTROWS('Entraînements') + 0", ENTIER),
        Mesure("Entraînements adoptés", e, compte("'Entraînements'", "'Entraînements'[Adopté] = 1"), ENTIER),
        Mesure("Modèle adopté", e, "CALCULATE(SELECTEDVALUE('Entraînements'[Essai], \"Aucun\"), "
                                   "REMOVEFILTERS('Entraînements'), 'Entraînements'[Adopté] = 1)"),
        Mesure("Meilleure erreur du modèle adopté", e,
               "CALCULATE(MIN('Entraînements'[Meilleure erreur de validation]), REMOVEFILTERS('Entraînements'), "
               "'Entraînements'[Adopté] = 1)", PERTE),
        Mesure("Exemples d'entraînement", e, "MAX('Entraînements'[Exemples d'entraînement])", ENTIER),
        Mesure("Erreur de validation", e, "AVERAGE('Courbe de validation'[Erreur de validation])", PERTE,
               "Erreur sur les exemples mis de côté, mesurée tous les 20 pas : elle doit baisser."),
        Mesure("Erreur au meilleur pas", e,
               "CALCULATE([Erreur de validation], 'Courbe de validation'[Meilleur] = 1)", PERTE),
        Mesure("Exemples réussis", e, "SUM(Scores[Réussis]) + 0", ENTIER),
        Mesure("Exemples testés", e, "SUM(Scores[Total]) + 0", ENTIER),
        Mesure("Taux de réussite", e, "DIVIDE(SUM(Scores[Réussis]), SUM(Scores[Total]))", PCT,
               "Exemples de test réussis ÷ exemples de test, par tâche et par modèle."),
    ]


def _pire_section(taux: str, effectif: str, seuil: int) -> str:
    """Libellé de la section au plus fort `taux`, parmi celles qui ont au moins `seuil` cas."""
    return (f"VAR s = FILTER(ADDCOLUMNS(VALUES('Sections'[Section]), \"t\", {taux}, \"n\", {effectif}), [n] >= {seuil})\n"
            "VAR p = TOPN(1, s, [t], DESC)\n"
            "RETURN MAXX(p, 'Sections'[Section])")


ACTIONS = [
    Action(1, "Contrôler les recommandations", "[Rapports en alerte] > 0", "Consultant",
           '"Contrôler " & [Rapports en alerte] & " rapport(s) d\'audit " & [Portée] & " : " & '
           '[Recommandations manquantes] + 0 & " recommandation(s) manquante(s) ou non détectée(s). '
           'Page Recommandations du dossier."',
           "au moins un rapport en alerte (trou ou doublon de numérotation, ou aucune recommandation détectée)"),
    Action(2, "Relancer la feuille de route", f"DIVIDE([Sorties invalides], [Appels feuille de route]) >= {SEUIL_INVALIDES}",
           "Consultant",
           '"Relancer la feuille de route : " & [Sorties invalides] & " réponse(s) du modèle au mauvais format sur " & '
           '[Appels feuille de route] & " appels."',
           f"sorties invalides ≥ {SEUIL_INVALIDES:.0%} des appels « axes » et « initiatives »"),
    Action(3, "Revoir les sources", f"[Taux de phrases non vérifiées] >= {SEUIL_NON_VERIFIEES}", "Consultant",
           '"Revoir les sources de « " & [Section la moins vérifiée] & " » : " & '
           'FORMAT([Taux de phrases non vérifiées], "0 %") & " des phrases non vérifiées sur le périmètre."',
           f"phrases non vérifiées ≥ {SEUIL_NON_VERIFIEES:.0%} ; la section désignée a au moins "
           f"{MIN_PHRASES_SECTION} phrases"),
    Action(4, "Compléter les documents", f"[Taux de refus] >= {SEUIL_REFUS}", "Consultant",
           '"Compléter les documents : le modèle refuse " & FORMAT([Taux de refus], "0 %") & '
           '" des sections faute de preuves, surtout « " & [Section la plus refusée] & " »."',
           f"sections refusées ≥ {SEUIL_REFUS:.0%} des sections demandées"),
    Action(5, "Relire", "[En relecture] > 0", "Responsable",
           '"Relire " & [En relecture] & " livrable(s) en attente de validation."',
           "au moins un livrable en relecture"),
    Action(6, "Reprendre les renvois", "[Renvoyés] > 0", "Consultant",
           '"Reprendre " & [Renvoyés] & " livrable(s) renvoyé(s) par le responsable."',
           "au moins un livrable renvoyé"),
    Action(7, "Valider les constats", "[Constats à valider] > 0", "Consultant",
           '"Valider " & [Constats à valider] & " constat(s) avant de produire la feuille de route."',
           "au moins un constat non validé"),
]
AUCUNE = "Rien d'urgent : aucune règle ne se déclenche sur ce périmètre."


def _texte(m: dict[str, str]) -> None:
    m["Mention données"] = ('VAR d = [Projets de démonstration]\nVAR r = [Projets réels]\n'
                            'RETURN IF(d = 0, "Données réelles", IF(r = 0, "[DÉMO] projets de démonstration", '
                            '"[DÉMO] " & r & " projet(s) réel(s) + " & d & " de démonstration"))')
    m["Badge démo"] = 'IF([Projets de démonstration] > 0, "[DÉMO] inclut des données de démonstration", "Données réelles")'
    m["Section la moins vérifiée"] = _pire_section(
        "DIVIDE([Phrases non vérifiées], [Phrases générées])", "[Phrases générées]", MIN_PHRASES_SECTION)
    m["Section la plus refusée"] = _pire_section("DIVIDE([Sections refusées], [Sections générées])",
                                                 "[Sections générées]", 3)
    lignes = ",\n".join(f'    ({a.rang}, IF({a.condition}, {a.texte} & "  [" & "{a.pour}" & "]", BLANK()))'
                        for a in ACTIONS)
    table = f"VAR t = FILTER({{\n{lignes}\n}}, NOT ISBLANK([Value2]))\n"
    m["Actions déclenchées"] = table + "RETURN COUNTROWS(t) + 0"
    m["Liste des actions"] = table + f'RETURN IF(COUNTROWS(t) = 0, "{AUCUNE}", CONCATENATEX(t, [Value2], " / ", [Value1], ASC))'
    for n in (1, 2, 3):
        # La n-ième règle déclenchée, par rang : le plus grand rang parmi les n premiers.
        vide = f'"{AUCUNE}"' if n == 1 else '""'
        m[f"Action {n}"] = (table + f"VAR r = IF(COUNTROWS(t) >= {n}, MAXX(TOPN({n}, t, [Value1], ASC), [Value1]))\n"
                            f"RETURN IF(ISBLANK(r), {vide}, MAXX(FILTER(t, [Value1] = r), [Value2]))")
        m[f"Numéro action {n}"] = f'IF([Actions déclenchées] >= {n}, "{n}", "")'
    m["Période"] = ('VAR d = MIN(Calendrier[Date])\nVAR f = MAX(Calendrier[Date])\n'
                    'RETURN "Du " & FORMAT(d, "dd/MM/yyyy") & " au " & FORMAT(f, "dd/MM/yyyy")')
    m["Périmètre"] = ('VAR p = IF(HASONEVALUE(Projets[Projet]), SELECTEDVALUE(Projets[Projet]), [Projets] & " projets")\n'
                      'VAR c = IF(HASONEVALUE(Projets[Client]), " · " & SELECTEDVALUE(Projets[Client]), "")\n'
                      'VAR k = IF(ISFILTERED(Personnes[Consultant]) && HASONEVALUE(Personnes[Consultant]), '
                      '" · " & SELECTEDVALUE(Personnes[Consultant]), "")\n'
                      'VAR t = IF(ISFILTERED(\'Types de livrable\'[Type de livrable]) && '
                      'HASONEVALUE(\'Types de livrable\'[Type de livrable]), " · " & '
                      'SELECTEDVALUE(\'Types de livrable\'[Type de livrable]), "")\n'
                      'RETURN [Période] & " · " & p & c & k & t')
    m["Pied de page"] = ("\"Traitement local · données au \" & FORMAT(CALCULATE(MAXX('Générations', "
                         'RELATED(Calendrier[Date])), REMOVEFILTERS()), "dd/MM/yyyy")')
    m["Titre du projet"] = ('IF(HASONEVALUE(Projets[Projet]), SELECTEDVALUE(Projets[Projet]), '
                            '"Choisissez un projet dans le filtre Projet")')
    m["Client du projet"] = 'IF(HASONEVALUE(Projets[Projet]), SELECTEDVALUE(Projets[Client]) & IF(SELECTEDVALUE(Projets[Secteur]) <> "", " · " & SELECTEDVALUE(Projets[Secteur]), ""), [Projets] & " projets dans le périmètre")'
    m["Demande du projet"] = ('IF(HASONEVALUE(Projets[Projet]), '
                              'VAR d = SELECTEDVALUE(Projets[Demande du client])\n'
                              'RETURN IF(d = "", "Demande du client non renseignée (fiche projet de l\'application)", '
                              '"Demande : " & d), "")')
    m["Dates du projet"] = ('IF(HASONEVALUE(Projets[Projet]), '
                            'VAR d = SELECTEDVALUE(Projets[Début])\nVAR f = SELECTEDVALUE(Projets[Fin])\n'
                            'RETURN IF(ISBLANK(d), "Dates non renseignées", "Début " & FORMAT(d, "dd/MM/yyyy") & '
                            'IF(ISBLANK(f), " · fin non fixée", " · fin " & FORMAT(f, "dd/MM/yyyy"))), "")')
    m["Recommandations sur annoncées"] = ('[Recommandations retenues] + 0 & " retenues sur " & '
                                          '[Recommandations annoncées] & " annoncées"')
    m["Note projets"] = 'IF([Projets de démonstration] > 0, "dont " & [Projets de démonstration] & " [DÉMO]", "réels")'
    m["Note livrables"] = '[En relecture] & " en relecture · " & [Renvoyés] & " renvoyé(s)"'
    m["Note erreur"] = ('[Appels en erreur] & " sur " & [Appels au modèle] + 0 & " · refus : " & '
                        'FORMAT([Taux de refus], "0 %")')
    m["Portée"] = ('IF(HASONEVALUE(Projets[Projet]), "dans ce projet", '
                   '"sur " & [Projets] & " projet(s)")')
    m["Temps moyen affiché"] = 'FORMAT([Temps moyen par appel], "0.0") & " s"'
    m["Citations sans source affiché"] = 'FORMAT([Taux de citations sans source], "0.0 %")'
    m["Meilleure erreur affichée"] = 'FORMAT([Meilleure erreur du modèle adopté], "0.000")'
    m["Note temps"] = '"par appel au modèle, PC local"'
    m["Note entraînements"] = '"dont " & [Entraînements adoptés] & " adopté : " & [Modèle adopté]'
    m["Note vérifiées"] = '[Phrases vérifiées] & " sur " & [Phrases générées]'
    m["Note citations"] = '[Citations sans source] & " sur " & [Citations générées]'
    m["Note refus"] = '"voulu, pas une erreur : " & [Sections refusées] & " sur " & [Sections générées]'
    m["Note invalides"] = '"sur " & [Appels feuille de route] & " appels de feuille de route"'
    m["Note recommandations"] = '[Recommandations validées] + 0 & " validées · " & [Recommandations à valider] + 0 & " à valider"'
    m["Note rapports"] = '[Portée] & " · " & [Rapports d\'audit] & " rapport(s) lu(s)"'
    m["Note constats"] = '[Constats à valider] & " à valider"'
    m["Note documents"] = '[Rapports d\'audit] & " rapport(s) d\'audit"'
    m["Note modèle adopté"] = '"meilleure erreur " & FORMAT([Meilleure erreur du modèle adopté], "0.000")'
    m["Note exemples"] = '"au plus, par entraînement"'
    m["Note essais"] = '"Colab et Kaggle, GPU T4 gratuit"'
    m["Note erreur adoptée"] = '"au meilleur pas (pas d\'arrêt anticipé)"'
    # Fiche d'entraînement (une ligne par essai)
    e = "'Entraînements'"
    m["Essai date"] = f'FORMAT(SELECTEDVALUE({e}[Date de l\'essai]), "dd/MM/yyyy")'
    m["Essai plateforme"] = f'SELECTEDVALUE({e}[Plateforme]) & " · " & SELECTEDVALUE({e}[GPU])'
    m["Essai exemples"] = f'FORMAT(SELECTEDVALUE({e}[Exemples d\'entraînement]), "#,0")'
    m["Essai durée"] = (f'VAR d = SELECTEDVALUE({e}[Durée en minutes])\n'
                        'RETURN IF(ISBLANK(d), "non consignée", FORMAT(d, "0") & " min")')
    m["Essai meilleure erreur"] = (f'VAR v = SELECTEDVALUE({e}[Meilleure erreur de validation])\n'
                                   f'VAR p = SELECTEDVALUE({e}[Meilleur pas])\n'
                                   'RETURN FORMAT(v, "0.000") & IF(ISBLANK(p), " (dernière mesure)", " au pas " & p)')
    m["Essai arrêt"] = f'"pas " & SELECTEDVALUE({e}[Pas d\'arrêt])'
    m["Essai décision"] = f'IF(SELECTEDVALUE({e}[Adopté]) = 1, "Adopté", "Non adopté")'
    m["Essai résultat"] = f'SELECTEDVALUE({e}[Résultat de l\'essai])'
    # Alertes de cohérence (une ligne par rapport en alerte)
    m["Alerte projet"] = 'IF(SUM(Rapports[En alerte]) > 0, SELECTEDVALUE(Rapports[Projet du rapport]))'
    m["Alerte annoncées"] = 'IF(SUM(Rapports[En alerte]) > 0, FORMAT(SUM(Rapports[Annoncées]), "0"))'
    m["Alerte retenues"] = 'IF(SUM(Rapports[En alerte]) > 0, FORMAT(SUM(Rapports[Retenues]), "0"))'
    m["Alerte manquants"] = ('IF(SUM(Rapports[En alerte]) > 0, VAR l = SELECTEDVALUE(Rapports[Numéros manquants])\n'
                             'RETURN IF(l = "", "—", "n° " & l))')
    m["Alerte contrôle"] = 'IF(SUM(Rapports[En alerte]) > 0, SELECTEDVALUE(Rapports[Contrôle]))'
    m["Couleur de l'alerte"] = f'IF(SUM(Rapports[En alerte]) > 0, "{ROUGE}")'
    m["Couleur de vague"] = (f'VAR n = [Initiatives]\nRETURN SWITCH(TRUE(), n >= 4, "{JAUNE}", n >= 2, "{JAUNE_MOYEN}", '
                             f'n >= 1, "{JAUNE_PALE}", "#FFFFFF")')
    m["Initiatives de la case"] = 'IF([Initiatives] > 0, [Initiatives])'


def presentation() -> list[Mesure]:
    m: dict[str, str] = {}
    _texte(m)
    return [Mesure(nom, "9. Présentation", dax, masquee=True) for nom, dax in m.items()]


def sous_titres(textes: dict[str, str]) -> list[Mesure]:
    """Sous-titres de visuels : le texte, puis la nature des données ([DÉMO] dès qu'un projet de démo est inclus)."""
    return [Mesure(f"ST {k}", "9. Présentation", f'"{v} · " & [Mention données]', masquee=True)
            for k, v in textes.items()]


SOUS_TITRES: dict[str, str] = {}  # rempli par rapport.py avant l'écriture du modèle


def toutes() -> list[Mesure]:
    return _base() + presentation() + sous_titres(SOUS_TITRES)


def kpi_md() -> str:
    out = [
        "# Indicateurs du tableau de bord Power BI", "",
        "> Fichier généré par `python bi/pbip/build_pbip.py` depuis [`pbip/indicateurs.py`](pbip/indicateurs.py).",
        "> Pages et visuels : [pages.md](pages.md). Qui voit quoi : [docs/14](../docs/14-acteurs-dashboard.md).", "",
        "Chaque visuel qui mélange projets réels et de démonstration le dit dans son sous-titre "
        "(« [DÉMO] 1 projet réel + 5 de démonstration »). Le filtre **Données** est réglé par défaut sur "
        f"« {TOUTES_DONNEES} ».", "", "## Indicateurs", "",
        "| Dossier | Indicateur | Définition | Format |", "|---|---|---|---|"]
    for x in _base():
        out.append(f"| {x.dossier[3:]} | **{x.nom}** | {x.description or '—'} | `{x.fmt or 'texte'}` |")
    out += ["", "## Que faire ensuite : règles d'action", "",
            "Règles explicites, sans modèle de langue, évaluées sur le périmètre filtré. Les 3 premières qui se "
            f"déclenchent s'affichent, dans l'ordre du rang ; sinon : « {AUCUNE} »", "",
            "| Rang | Action | Pour | Se déclenche quand |", "|---:|---|---|---|"]
    out += [f"| {a.rang} | {a.nom} | {a.pour} | {a.regle} |" for a in ACTIONS]
    out += ["", "## Formules DAX", ""]
    for x in _base():
        out += [f"### {x.nom}", "", "```dax", f"{x.nom} =", x.dax, "```", ""]
    out += ["### Liste des actions", "", "```dax", "Liste des actions =",
            next(m.dax for m in presentation() if m.nom == "Liste des actions"), "```"]
    return "\n".join(out) + "\n"


def measures_dax() -> str:
    out = ["// Mesures du rapport Power BI. GÉNÉRÉ par bi/pbip/build_pbip.py : modifier bi/pbip/indicateurs.py.",
           "// Les noms de tables et de colonnes sont ceux du modèle CadrageIA ; définitions dans bi/KPI.md.", ""]
    for x in _base() + [m for m in presentation() if m.nom.startswith(("Liste des actions", "Action ", "Mention"))]:
        out += [f"// {ligne}" for ligne in x.description.split("\n") if ligne]
        out += [f"{x.nom} =", x.dax, ""]
    return "\n".join(out)
