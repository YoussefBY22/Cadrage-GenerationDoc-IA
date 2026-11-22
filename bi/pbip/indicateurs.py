"""Indicateurs du rapport Power BI : source unique des mesures, de `bi/measures.dax` et de `bi/KPI.md`.

Seuils, règles de recommandation et méthode de prédiction viennent de `backend/app/dw/pilotage.py`,
aussi utilisé par l'ETL et par la commande de rapport : Power BI ne fait que compter et afficher.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "app" / "dw"))
import pilotage  # noqa: E402  (bibliothèque standard seulement)

ANTHRACITE, GRIS, GRIS_CLAIR, JAUNE = "#2E2E38", "#747480", "#C4C4CD", "#FFE600"
GRIS_TEXTE = "#5F5F6B"  # le gris de la charte n'atteint pas 4,5:1 sur le fond (4,28) : réservé aux aplats
ROUGE = "#B4232F"  # jamais opposé à un vert (accessibilité) : le favorable se lit en gras et en toutes lettres
FOND_ROUGE, FOND_GRIS, FOND_BLANC = "#F6D5D8", "#E9E9EF", "#FFFFFF"

TOUS, TOUT = "Tous", "Tout l'historique"
PCT, ENTIER, JOURS = "0 %", "#,0", '0 "j"'
N_MIN = pilotage.MIN_SAMPLE
RETARD = pilotage.REVIEW_OVERDUE_HOURS
CONSULTANT, RESPONSABLE, RAPPORT, ADMINISTRATION = "Consultant", "Responsable", "Rapport", "Administration"
SUFFIXE = {None: "", CONSULTANT: " (consultant)", RESPONSABLE: " (responsable)"}
FLUX = "Flux : suit la période."
INSTANT = "Situation à la date des données : ne suit pas la période."


@dataclass(frozen=True)
class Kpi:
    nom: str
    acteur: str
    formule: str
    decision: str
    cible: str
    portee: str
    limite: str = ""

    @property
    def description(self) -> str:
        texte = f"Formule : {self.formule}\nDécision : {self.decision}\nCible : {self.cible}\n{self.portee}"
        return texte + (f"\nLimite : {self.limite}" if self.limite else "")


@dataclass(frozen=True)
class Mesure:
    nom: str
    dossier: str
    dax: str
    fmt: str | None = None
    description: str = ""
    masquee: bool = False


# Au plus 4 KPI par page acteur, chacun lié à une décision
KPIS: list[Kpi] = [
    Kpi("Livrables à traiter", CONSULTANT,
        "livrables en brouillon ou renvoyés, dont les renvois pas encore resoumis.",
        "Par quel livrable commencer", "aucun seuil dans H7", INSTANT),
    Kpi("Phrases bloquantes à corriger", CONSULTANT,
        "phrases des livrables chez le consultant dont la source est absente du dossier, ou rejetées "
        "par le vérificateur et inchangées depuis.",
        "Quoi corriger avant de soumettre", "0 avant de soumettre (règle du produit)", INSTANT,
        "une phrase modifiée n'est pas revérifiée ici : seule sa source est contrôlée."),
    Kpi("Sections acceptées sans retouche", CONSULTANT,
        "sections approuvées mot pour mot ÷ sections rédigées puis approuvées (refus exclus).",
        "Partir du premier jet ou le retravailler",
        f"au moins {pilotage.H7_REUSABLE * 100:.0f} % (H7)", FLUX,
        f"H7 raisonne par phrase, l'entrepôt par section (plus sévère). Pas de taux sous {N_MIN} sections."),

    Kpi("Livrables à valider", RESPONSABLE,
        f"livrables en relecture, dont ceux qui attendent depuis plus de {RETARD} h.",
        "Qui relit quoi aujourd'hui", f"0 au-delà de {RETARD} h (règle de pilotage, hors H7)", INSTANT),
    Kpi("Délai de validation", RESPONSABLE,
        "médiane des heures entre la première soumission et l'approbation.",
        "Renforcer ou répartir la relecture", "aucun seuil dans H7", FLUX,
        f"heures calendaires ; pas de valeur sous {N_MIN} livrables ; ne voit pas ce qui attend encore."),
    Kpi("Renvois à la première relecture", RESPONSABLE,
        "livrables renvoyés à leur première relecture ÷ livrables dont la première relecture est décidée.",
        "Revoir la préparation avant soumission", "aucun seuil dans H7", FLUX,
        f"pas de taux sous {N_MIN} décisions."),
    Kpi("Phrases bloquantes à vérifier", RESPONSABLE,
        "phrases bloquantes, non acquittées, des livrables en relecture.",
        "Quoi vérifier en premier", "0 à l'approbation (règle du produit)", INSTANT),

    Kpi("Citations sans source après approbation", RAPPORT,
        "citations de la version approuvée dont la source n'est pas dans le dossier.",
        "Autoriser ou bloquer l'envoi au client", f"{pilotage.H7_INVALID_LEFT} (H7)", FLUX,
        "« non mesuré » si la version approuvée n'a pas de sections lisibles ; "
        "qu'une source existe ne prouve pas qu'elle soutient la phrase."),
    Kpi("Citations sans source avant relecture", RAPPORT,
        "citations générées dont la source n'est pas dans le dossier ÷ citations générées.",
        "Régler la recherche ou le modèle",
        "aucune : le critère H7 porte sur ce qui reste après approbation", FLUX),
    Kpi("Phrases vérifiées", RAPPORT,
        "phrases validées par le vérificateur ÷ phrases générées (TPV).",
        "Effort de relecture à prévoir", "aucune : H7 ne fixe pas de seuil sur le TPV", FLUX,
        "mesure l'ancrage dans les sources, pas la vérité."),

    Kpi("Alertes d'injection", ADMINISTRATION,
        "consignes cachées détectées dans les documents importés.",
        "Examiner chaque passage signalé", "examiner toutes les alertes", INSTANT,
        "une alerte est une détection, pas une attaque réussie."),
    Kpi("Documents signalés", ADMINISTRATION,
        "documents avec au moins une alerte d'injection ÷ documents importés.",
        "Revoir une source documentaire", "examiner toutes les alertes", INSTANT,
        f"pas de taux sous {N_MIN} documents."),
]


DEMO = "MAX('Source des données'[Est une démonstration]) = 1"


def mesure_reelle(valeur: str, sinon: str = "BLANK()") -> str:
    """Une mesure de qualité du modèle n'existe pas sur des données inventées."""
    return f"IF({DEMO}, {sinon}, {valeur})"


def entier(expr: str) -> str:
    return f'FORMAT({expr}, "#,0", "fr-FR")'


def effectif(part: str, total: str, quoi: str) -> str:
    return (f"VAR vPart = {part} + 0\nVAR vN = {total} + 0\n"
            f'RETURN IF(vN < {N_MIN}, "Effectif insuffisant (n = " & vN & ")", '
            f'{entier("vPart")} & " sur " & {entier("vN")} & " {quoi}")')


def _etats(*codes: str) -> str:
    valeurs = ", ".join(f'"{c}"' for c in codes)
    return f"KEEPFILTERS(Livrables[Code d'état] IN {{{valeurs}}})"


CHEZ_CONSULTANT, EN_RELECTURE, APPROUVE = _etats("draft", "rejected"), _etats("in_review"), _etats("approved")
PAR_APPROBATION = "USERELATIONSHIP(Livrables[Clé d'approbation], Calendrier[Clé de date])"
PAR_SOUMISSION = "USERELATIONSHIP(Livrables[Clé de soumission], Calendrier[Clé de date])"


def _appui() -> list[Mesure]:
    sections = "'Sections approuvées'"
    redigee = f"KEEPFILTERS({sections}[Refusée] = 0)"
    generee = "KEEPFILTERS('Générations'[Statut] = \"ok\"), KEEPFILTERS('Générations'[Code du type] <> \"findings\")"
    c, r, p, a = CONSULTANT, RESPONSABLE, RAPPORT, ADMINISTRATION
    return [
        Mesure("Livrables à traiter", c, f"CALCULATE(COUNTROWS(Livrables), {CHEZ_CONSULTANT}) + 0", ENTIER),
        Mesure("Renvois à reprendre", c,
               f"CALCULATE(COUNTROWS(Livrables), {CHEZ_CONSULTANT}, KEEPFILTERS(Livrables[Renvoyé] = 1)) + 0", ENTIER),
        Mesure("Phrases bloquantes à corriger", c,
               f"CALCULATE(SUM(Livrables[Phrases bloquantes]), {CHEZ_CONSULTANT}) + 0", ENTIER),
        Mesure("Sections rédigées puis approuvées", c, f"CALCULATE(COUNTROWS({sections}), {redigee}) + 0", ENTIER),
        Mesure("Nombre de sections sans retouche", c,
               f"CALCULATE(COUNTROWS({sections}), {redigee}, KEEPFILTERS({sections}[Sans retouche] = 1)) + 0", ENTIER),
        Mesure("Sections acceptées sans retouche", c,
               "VAR vN = [Sections rédigées puis approuvées]\n"
               "RETURN " + mesure_reelle(
                   f"IF(vN >= {N_MIN}, DIVIDE([Nombre de sections sans retouche], vN))"), PCT),

        Mesure("Livrables à valider", r, f"CALCULATE(COUNTROWS(Livrables), {EN_RELECTURE}) + 0", ENTIER),
        Mesure("Relectures en retard", r,
               f"CALCULATE(COUNTROWS(Livrables), {EN_RELECTURE}, "
               f"KEEPFILTERS(Livrables[Heures dans l'état] > {RETARD})) + 0", ENTIER),
        Mesure("Phrases bloquantes à vérifier", r,
               f"CALCULATE(SUM(Livrables[Phrases bloquantes]), {EN_RELECTURE}) + 0", ENTIER),
        Mesure("Livrables avec délai", r,
               f"CALCULATE(COUNT(Livrables[Délai en heures]), {APPROUVE}, {PAR_APPROBATION}) + 0", ENTIER),
        Mesure("Délai de validation", r,
               f"IF([Livrables avec délai] >= {N_MIN}, "
               f"CALCULATE(MEDIAN(Livrables[Délai en heures]), {APPROUVE}, {PAR_APPROBATION}))", '0 "h"'),
        Mesure("Premières relectures décidées", r,
               f"CALCULATE(COUNT(Livrables[Renvoyé en première relecture]), {PAR_SOUMISSION}) + 0", ENTIER),
        Mesure("Nombre de renvois en première relecture", r,
               f"CALCULATE(SUM(Livrables[Renvoyé en première relecture]), {PAR_SOUMISSION}) + 0", ENTIER),
        Mesure("Renvois à la première relecture", r,
               f"VAR vN = [Premières relectures décidées]\n"
               f"RETURN IF(vN >= {N_MIN}, DIVIDE([Nombre de renvois en première relecture], vN))", PCT),

        Mesure("Livrables approuvés", p, f"CALCULATE(COUNTROWS(Livrables), {APPROUVE}, {PAR_APPROBATION}) + 0", ENTIER),
        Mesure("Livrables mesurés", p,
               f"CALCULATE(COUNT(Livrables[Citations finales]), {APPROUVE}, {PAR_APPROBATION}) + 0", ENTIER),
        Mesure("Citations approuvées", p,
               f"CALCULATE(SUM(Livrables[Citations finales]), {APPROUVE}, {PAR_APPROBATION})", ENTIER),
        Mesure("Citations sans source après approbation", p,
               mesure_reelle(
                   "IF([Livrables mesurés] > 0, "
                   f"CALCULATE(SUM(Livrables[Citations sans source]), {APPROUVE}, {PAR_APPROBATION}) + 0)"), ENTIER),
        Mesure("Citations générées", p, f"CALCULATE(SUM('Générations'[Citations produites]), {generee}) + 0", ENTIER),
        Mesure("Nombre de citations sans source avant relecture", p,
               "[Citations générées] - CALCULATE(SUM('Générations'[Citations valides en nombre]), "
               f"{generee})", ENTIER),
        Mesure("Citations sans source avant relecture", p,
               mesure_reelle(f"IF([Citations générées] >= {N_MIN}, "
                             "DIVIDE([Nombre de citations sans source avant relecture], [Citations générées]))"),
               PCT),
        Mesure("Phrases générées", p, f"CALCULATE(SUM('Générations'[Phrases produites]), {generee}) + 0", ENTIER),
        Mesure("Nombre de phrases vérifiées", p,
               f"CALCULATE(SUM('Générations'[Phrases validées]), {generee}) + 0", ENTIER),
        Mesure("Phrases vérifiées", p,
               mesure_reelle(
                   f"IF([Phrases générées] >= {N_MIN}, DIVIDE([Nombre de phrases vérifiées], [Phrases générées]))"),
               PCT),

        Mesure("Alertes d'injection", a, "SUM(Documents[Alertes]) + 0", ENTIER),
        Mesure("Documents analysés", a, "COUNTROWS(Documents)", ENTIER),
        Mesure("Nombre de documents signalés", a,
               "IF([Documents analysés] > 0, "
               "CALCULATE(COUNTROWS(Documents), KEEPFILTERS(Documents[Alertes] > 0)) + 0)", ENTIER),
        Mesure("Documents signalés", a,
               f"IF([Documents analysés] >= {N_MIN}, DIVIDE([Nombre de documents signalés], [Documents analysés]))", PCT),
    ]


def _recommandations(m: dict[str, str]) -> None:
    for acteur, suffixe in SUFFIXE.items():
        regles = "'Règles'" if acteur is None else f"FILTER('Règles', 'Règles'[Acteur] = \"{acteur}\")"
        for i in range(1, pilotage.MAX_RECOMMENDATIONS + 1):
            debut = (
                f"VAR vListe = FILTER(ADDCOLUMNS({regles}, \"@n\",\n"
                "    VAR vCode = 'Règles'[Code de règle]\n"
                "    RETURN CALCULATE(COUNTROWS(Actions), Actions[Code de règle signalée] = vCode)), [@n] > 0)\n"
                f"VAR vPremiers = TOPN({i}, vListe, 'Règles'[Priorité], ASC)\n"
                "VAR vLigne = TOPN(1, vPremiers, 'Règles'[Priorité], DESC)\n")
            rien = '"Aucune règle ne se déclenche sur ce périmètre."' if i == 1 else '" "'
            m[f"Reco {i} constat{suffixe}"] = debut + (
                "VAR vEtats = MAXX(vLigne, 'Règles'[États])\n"
                "VAR vTotal = CALCULATE(COUNTROWS(Livrables),\n"
                "    KEEPFILTERS(FILTER(ALL(Livrables[Code d'état]), CONTAINSSTRING(vEtats, Livrables[Code d'état]))))\n"
                f"RETURN IF(COUNTROWS(vPremiers) < {i}, {rien},\n"
                f'    "{i}. " & MAXX(vLigne, \'Règles\'[Libellé]) & " : " & MAXX(vLigne, [@n]) & " sur "\n'
                "    & (vTotal + 0) & \" (\" & MAXX(vLigne, 'Règles'[Population]) & \")\")")
            pour = "\"Pour le \" & LOWER(MAXX(vLigne, 'Règles'[Acteur])) & \" : \" & " if acteur is None else ""
            m[f"Reco {i} action{suffixe}"] = debut + (
                f'RETURN IF(COUNTROWS(vPremiers) < {i}, " ",\n'
                f"    {pour}MAXX(vLigne, 'Règles'[Action]) & UNICHAR(10)\n"
                "    & \"Seuil : \" & MAXX(vLigne, 'Règles'[Seuil]))")


def _prediction(m: dict[str, str]) -> None:
    # Parmi les périmètres visibles, le plus général. Sous RLS, seuls ceux de la personne sont visibles :
    # un consultant lit donc sa prévision, un responsable la sienne, et jamais le total du cabinet.
    ici = (f"VAR vClient = SELECTEDVALUE('Choix du client'[Client choisi], \"{TOUS}\")\n"
           f"VAR vType = SELECTEDVALUE('Choix du type'[Type choisi], \"{TOUS}\")\n"
           f"VAR vPersonne = SELECTEDVALUE('Choix du consultant'[Consultant choisi], \"{TOUS}\")\n"
           "VAR vCandidats = FILTER(ALL('Prévisions'), 'Prévisions'[Périmètre client] = vClient\n"
           f"    && 'Prévisions'[Périmètre type] = vType && (vPersonne = \"{TOUS}\"\n"
           "        || 'Prévisions'[Périmètre consultant] = vPersonne))\n"
           "VAR vPrevision = TOPN(1, vCandidats, 'Prévisions'[Rang de périmètre], ASC, "
           "'Prévisions'[Clé de prévision], ASC)\n"
           "VAR vStatut = MAXX(vPrevision, 'Prévisions'[Statut de prévision])\n")

    def colonne(nom: str) -> str:
        return f"MAXX(vPrevision, 'Prévisions'[{nom}])"

    def arrondi(nom: str, fmt: str = "0") -> str:
        return f'FORMAT({colonne(nom)}, "{fmt}", "fr-FR")'

    niveau = f"{pilotage.INTERVAL * 100:.0f} %"
    for nom, champ in (("Soumissions réelles", "Réel"), ("Prévision", "Point prévu"),
                       ("Borne basse", "Borne basse prévue"), ("Borne haute", "Borne haute prévue")):
        m[nom] = ici + (f"VAR vCle = {colonne('Clé de prévision')}\n"
                        f"RETURN CALCULATE(SUM('Série de prévision'[{champ}]), "
                        "'Série de prévision'[Clé de prévision] = vCle)")
    m["Prévision valeur"] = ici + (
        f'RETURN SWITCH(vStatut, "ok", {arrondi("Point")} & " soumissions attendues, entre " & {arrondi("Bas")}'
        f' & " et " & {arrondi("Haut")} & " (intervalle de {niveau})",\n'
        '    "not_better", "Pas de prévision fiable", "Historique insuffisant")')
    m["Prévision méthode"] = ici + (
        'RETURN SWITCH(vStatut, "ok", '
        f'"Moyenne des {pilotage.WINDOW_WEEKS} dernières semaines, n = " & {arrondi("Soumissions")}'
        f' & " soumissions. Test rétrospectif : erreur de " & {arrondi("Erreur", "0.0")}'
        f' & ", contre " & {arrondi("Erreur naïve", "0.0")} & " pour la référence naïve ("'
        f' & {arrondi("Origines")} & " prévisions).",\n'
        '    "not_better", "La méthode ne fait pas mieux que répéter les 2 dernières semaines.",\n'
        f'    "Il faut au moins {N_MIN} soumissions et {pilotage.MIN_ORIGINS} prévisions vérifiables.")')
    m["Prévision risque"] = ici + (
        'RETURN SWITCH(MAXX(vPrevision, \'Prévisions\'[Statut du risque]),\n'
        f'    "ok", "Risque de renvoi : testé sur " & {arrondi("Cas testés")} & " cas passés, score de Brier "\n'
        f'        & {arrondi("Brier", "0.000")} & ", contre " & {arrondi("Brier naïf", "0.000")}'
        ' & " pour le taux global",\n'
        '    "not_better", "Risque de renvoi non publié : il ne fait pas mieux que le taux global",\n'
        '    "Risque de renvoi non publié : historique insuffisant")')
    m["Mention simulation"] = (
        "IF(MAX(\'Source des données\'[Est une démonstration]) = 1,\n"
        '    "Simulation sur données inventées", " ")')


def presentation() -> list[Mesure]:
    m: dict[str, str] = {}
    _recommandations(m)
    _prediction(m)

    demo = "MAX('Source des données'[Est une démonstration]) = 1"
    m["Bandeau données"] = f'IF({demo}, "Données de démonstration · valeurs inventées", " ")'
    m["Pied de page"] = f'IF({demo}, "Traitement local · jeu inventé", "Traitement local · confidentiel")'
    jour = ('VAR vDate = MAX(\'Source des données\'[Date de situation])\n'
            'VAR vJour = MID(vDate, 9, 2) & "/" & MID(vDate, 6, 2) & "/" & LEFT(vDate, 4)\n')
    client = f'SELECTEDVALUE(\'Choix du client\'[Client choisi], "{TOUS}")'
    kind = f'SELECTEDVALUE(\'Choix du type\'[Type choisi], "{TOUS}")'
    personne = f'SELECTEDVALUE(\'Choix du consultant\'[Consultant choisi], "{TOUS}")'
    periode = f'SELECTEDVALUE(\'Choix de période\'[Période choisie], "{TOUT}")'
    perimetre = f'"Client : " & {client} & "  ·  type : " & {kind} & "  ·  consultant : " & {personne}'
    quand = f'"  |  " & {periode} & ", situation au " & vJour'

    # Sous-titres : périmètre, mesure, période
    for page, mesures in (("synthese", "livrables en nombre, délai en heures"),
                          ("production", "livrables et phrases en nombre, sections en %"),
                          ("validation", "livrables en nombre, attente en jours, délai en heures"),
                          ("administration", "phrases, citations et documents en % et en nombre")):
        m[f"Sous-titre {page}"] = jour + f'RETURN {perimetre} & "  |  {mesures}" & {quand}'
    m["Filtres du rapport"] = jour + f'RETURN {perimetre} & {quand}'

    # Constats : le message vit dans sa zone, jamais dans un titre
    accord = 'IF({0} > 1, " livrables attendent", " livrable attend")'
    livrables = 'IF({0} > 1, " livrables", " livrable")'
    phrases = 'IF({0} > 1, " phrases bloquantes", " phrase bloquante")'
    m["Constat synthese"] = (
        "VAR vFile = [Livrables à valider]\nVAR vRetard = [Relectures en retard]\n"
        "VAR vReste = [Citations sans source après approbation]\n"
        'RETURN IF(vFile = 0, "Aucun livrable en attente de relecture. ", vFile & ' + accord.format("vFile")
        + f' & " une relecture, dont " & vRetard & " depuis plus de {RETARD} h. ")\n'
        '    & IF(ISBLANK(vReste), "Citations après approbation : non mesuré.",\n'
        '        IF(vReste > 0, vReste & IF(vReste > 1, " citations sans source restent", " citation sans source reste")\n'
        '            & " après approbation.",\n'
        '            "Aucune citation sans source dans les livrables approuvés mesurés."))')
    m["Constat production"] = (
        "VAR vTodo = [Livrables à traiter]\n"
        'RETURN IF(vTodo = 0, "Aucun livrable à traiter sur ce périmètre.",\n'
        '    vTodo & ' + livrables.format("vTodo") + ' & " à traiter, dont " & [Renvois à reprendre]'
        + ' & IF([Renvois à reprendre] > 1, " renvoyés. ", " renvoyé. ")\n'
        '    & [Phrases bloquantes à corriger] & ' + phrases.format("[Phrases bloquantes à corriger]")
        + ' & " à corriger avant de soumettre.")')
    m["Constat validation"] = (
        "VAR vFile = [Livrables à valider]\n"
        'RETURN IF(vFile = 0, "Aucun livrable en attente de relecture sur ce périmètre.",\n'
        '    vFile & ' + livrables.format("vFile")
        + f' & " à valider, dont " & [Relectures en retard] & " depuis plus de {RETARD} h. "\n'
        '    & [Phrases bloquantes à vérifier] & ' + phrases.format("[Phrases bloquantes à vérifier]")
        + ' & " à vérifier avant d\'approuver.")')
    m["Constat administration"] = (
        'VAR vAlertes = [Alertes d\'injection]\n'
        'RETURN [Banc décision] & ". " & vAlertes & IF(vAlertes > 1, " alertes", " alerte")\n'
        '    & " d\'injection, dans " & ([Nombre de documents signalés] + 0) & " documents à examiner."')

    # --- cartes : valeur numérique (épinglable avec alerte dans le Service), effectif en sous-titre
    m["Note Livrables à traiter"] = '"dont " & [Renvois à reprendre] & IF([Renvois à reprendre] > 1, " renvoyés", " renvoyé")'
    m["Note Phrases bloquantes à corriger"] = '"sur " & [Livrables à traiter] & IF([Livrables à traiter] > 1, " livrables", " livrable") & " à traiter"'
    m["Note Sections acceptées sans retouche"] = effectif(
        "[Nombre de sections sans retouche]", "[Sections rédigées puis approuvées]",
        f"· cible H7 ≥ {pilotage.H7_REUSABLE * 100:.0f} %")
    m["Note Livrables à valider"] = f'"dont " & [Relectures en retard] & " depuis plus de {RETARD} h"'
    m["Note Délai de validation"] = (
        f'VAR vN = [Livrables avec délai]\nRETURN IF(vN < {N_MIN}, "Effectif insuffisant (n = " & vN & ")",\n'
        '    "médiane, n = " & vN & " livrables")')
    m["Note Renvois à la première relecture"] = effectif(
        "[Nombre de renvois en première relecture]", "[Premières relectures décidées]", "relectures")
    m["Note Phrases bloquantes à vérifier"] = '"sur " & [Livrables à valider] & IF([Livrables à valider] > 1, " livrables", " livrable") & " en relecture"'
    m["Note Citations sans source après approbation"] = (
        "VAR vN = [Livrables mesurés]\n"
        'RETURN IF(vN = 0, "Non mesuré", "sur " & ' + entier("[Citations approuvées]")
        + ' & " citations, " & vN & IF(vN > 1, " livrables mesurés", " livrable mesuré"))')
    m["Note Citations sans source avant relecture"] = effectif(
        "[Nombre de citations sans source avant relecture]", "[Citations générées]", "citations")
    m["Note Phrases vérifiées"] = effectif("[Nombre de phrases vérifiées]", "[Phrases générées]", "phrases")
    m["Note Documents signalés"] = effectif("[Nombre de documents signalés]", "[Documents analysés]", "documents")
    m["Note Alertes d'injection"] = '"dans " & ([Nombre de documents signalés] + 0) & " documents"'

    # --- tableaux acteurs : une mesure vide retire la ligne
    m["À traiter état"] = f"CALCULATE(SELECTEDVALUE(Livrables[État]), {CHEZ_CONSULTANT})"
    si_traite = "IF(NOT ISBLANK([À traiter état]), "
    m["À traiter motif"] = si_traite + 'COALESCE(SELECTEDVALUE(Livrables[Motif du renvoi]), "—"))'
    m["À traiter bloquantes"] = si_traite + "SUM(Livrables[Phrases bloquantes]) + 0)"
    m["À traiter sans preuve"] = si_traite + "SUM(Livrables[Sections sans preuve]) + 0)"
    m["À traiter inactivité"] = si_traite + "MAX(Livrables[Heures sans activité]) / 24)"

    m["Section priorité"] = (
        f"VAR v = CALCULATE(SUM('Sections courantes'[Priorité de section]), {CHEZ_CONSULTANT})\n"
        "RETURN IF(v > 0, v)")
    si_section = "IF(NOT ISBLANK([Section priorité]), "
    m["Section bloquantes"] = si_section + f"CALCULATE(SUM('Sections courantes'[Bloquantes]), {CHEZ_CONSULTANT}) + 0)"
    m["Section sans source"] = si_section + f"CALCULATE(SUM('Sections courantes'[Sans source]), {CHEZ_CONSULTANT}) + 0)"
    m["Section refus"] = si_section + (
        f'IF(CALCULATE(SUM(\'Sections courantes\'[Refus]), {CHEZ_CONSULTANT}) > 0, "Ajouter une preuve", "Corriger"))')

    # Une mesure vide, et non 0, retire de la charge les consultants hors du filtre
    m["Charge en relecture"] = "VAR v = [Livrables à valider]\nRETURN IF(v > 0, v)"
    m["Charge chez le consultant"] = "VAR v = [Livrables à traiter]\nRETURN IF(v > 0, v)"
    m["File attente"] = f"CALCULATE(MAX(Livrables[Heures dans l'état]), {EN_RELECTURE}) / 24"
    si_file = "IF(NOT ISBLANK([File attente]), "
    m["File priorité"] = si_file + (
        f"[File attente] * (1 + IF({DEMO}, 0, COALESCE(MAX(Livrables[Risque]), 0))))")
    m["File consultant"] = si_file + "CALCULATE(SELECTEDVALUE(Personnes[Consultant]), CROSSFILTER(Livrables[Clé de consultant], Personnes[Clé de personne], BOTH)))"
    m["File bloquantes"] = si_file + "SUM(Livrables[Phrases bloquantes]) + 0)"
    m["File risque"] = si_file + (
        f'IF({DEMO}, "Non mesuré", '
        'IF(ISBLANK(MAX(Livrables[Risque])), "non estimé", FORMAT(MAX(Livrables[Risque]), "0 %") & " ["\n'
        '    & FORMAT(MAX(Livrables[Risque bas]), "0 %") & " à " & FORMAT(MAX(Livrables[Risque haut]), "0 %")\n'
        '    & "], n = " & MAX(Livrables[Risque effectif]))))')
    m["Couleur d'attente"] = (
        f'VAR v = [File attente]\nRETURN IF(NOT ISBLANK(v), IF(v * 24 > {RETARD}, "{FOND_ROUGE}", "{FOND_BLANC}"))')
    m["Couleur de blocage"] = f'IF([File bloquantes] > 0, "{FOND_GRIS}", "{FOND_BLANC}")'
    m["Couleur de correction"] = f'IF([À traiter bloquantes] > 0, "{FOND_ROUGE}", "{FOND_BLANC}")'

    # --- rapport imprimable
    cible = f"cible ≥ {pilotage.H7_REUSABLE * 100:.0f} %"
    m["H7 citations"] = (
        "VAR vN = [Livrables mesurés]\nVAR vReste = [Citations sans source après approbation]\n"
        'RETURN IF(vN = 0, "Non mesuré", vReste & " sur " & ' + entier("[Citations approuvées]")
        + ' & " citations (" & vN & IF(vN > 1, " livrables", " livrable") & ") · cible 0 · "\n'
        f'    & IF(vReste > {pilotage.H7_INVALID_LEFT}, "non atteint",\n'
        '        IF(vN < [Livrables approuvés], "non mesuré en totalité",\n'
        f'            IF(vN < {N_MIN}, "effectif insuffisant pour conclure", "atteint"))))')
    m["H7 retouche"] = (
        "VAR vN = [Sections rédigées puis approuvées]\nVAR vTaux = [Sections acceptées sans retouche]\n"
        f'RETURN IF(vN < {N_MIN}, "Effectif insuffisant (n = " & vN & ")",\n'
        f'    FORMAT(vTaux, "0 %") & " (" & [Nombre de sections sans retouche] & " sur " & vN & ") · {cible} · "\n'
        f'    & IF(vTaux >= {pilotage.H7_REUSABLE}, "atteint", "non atteint") & ", approximation par section")')
    m["Rapport synthèse"] = (
        '[Livrables à valider] & " livrables attendent une relecture, dont " & [Relectures en retard]\n'
        f'    & " depuis plus de {RETARD} h. " & [Livrables à traiter] & " sont chez les consultants, dont "\n'
        '    & [Renvois à reprendre] & " renvois à reprendre."')
    m["Rapport file"] = '[Livrables à valider] & IF([Livrables à valider] > 1, " livrables", " livrable") & ", dont " & [Relectures en retard] & " en retard"'
    m["Rapport délai"] = (
        "VAR v = [Délai de validation]\n"
        'RETURN IF(ISBLANK(v), [Note Délai de validation],\n'
        '    FORMAT(v, "0.0", "fr-FR") & " h (" & [Note Délai de validation] & ")")')
    m["Rapport renvois"] = (
        "VAR v = [Renvois à la première relecture]\n"
        'RETURN IF(ISBLANK(v), [Note Renvois à la première relecture],\n'
        '    FORMAT(v, "0 %") & " (" & [Note Renvois à la première relecture] & ")")')
    m["Rapport bloquantes"] = (
        '[Phrases bloquantes à vérifier] & " en relecture, " & [Phrases bloquantes à corriger]'
        ' & " chez les consultants"')
    m["Rapport vérifiées"] = (
        f'VAR vN = [Phrases générées]\nRETURN IF(vN < {N_MIN}, "Effectif insuffisant",\n'
        f'    FORMAT([Phrases vérifiées], "0 %") & " de " & {entier("vN")} & " phrases générées")')
    m["Rapport détectées"] = (
        f'VAR vN = [Citations générées]\nRETURN IF(vN < {N_MIN}, "Effectif insuffisant",\n'
        '    FORMAT([Citations sans source avant relecture], "0.0 %", "fr-FR") & " ("\n'
        f'    & [Nombre de citations sans source avant relecture] & " sur " & {entier("vN")} & ")")')

    # --- administration
    m["Banc décision"] = (
        'VAR vRetenues = FILTER(ALL(Banc), Banc[Code de décision] = "retain")\n'
        "VAR vMesurees = COUNTROWS(FILTER(ALL(Banc), NOT ISBLANK(Banc[TPV]))) + 0\n"
        "VAR vNombre = COUNTROWS(vRetenues) + 0\n"
        'RETURN IF(vMesurees = 0, "Banc d\'essai non mesuré",\n'
        f'    IF(vNombre = 0, "Rester sur {pilotage.REFERENCE_CONFIG} : aucun écart favorable concluant",\n'
        '        "Écart concluant pour : " & CONCATENATEX(vRetenues, Banc[Configuration], ", ")))')
    m["Banc montage"] = "SELECTEDVALUE(Banc[Montage])"
    m["Banc effectif"] = "MAX(Banc[Sections du banc])"
    m["Banc TPV"] = (
        "IF(COUNTROWS(Banc) = 1, IF(ISBLANK(MAX(Banc[TPV])), \"Non mesuré\", FORMAT(MAX(Banc[TPV]), \"0 %\")\n"
        '    & " [" & FORMAT(MAX(Banc[TPV bas]), "0 %") & " à " & FORMAT(MAX(Banc[TPV haut]), "0 %") & "]"))')
    ecart = 'FORMAT(100 * MAX(Banc[{}]), "+0.0;-0.0;0.0", "fr-FR")'
    m["Banc écart"] = (
        "IF(COUNTROWS(Banc) = 1, IF(ISBLANK(MAX(Banc[Écart])), \"—\",\n"
        f'    {ecart.format("Écart")} & " [" & {ecart.format("Écart bas")} & " à " & {ecart.format("Écart haut")} & "]"))')
    m["Banc citations"] = (
        'VAR v = MAX(Banc[Citations valides])\nRETURN IF(NOT ISBLANK(v), FORMAT(v, "0.0 %", "fr-FR"))')
    m["Banc chiffres"] = "MAX(Banc[Chiffres fidèles])"
    m["Banc attaque"] = "MAX(Banc[Attaques réussies])"
    m["Banc latence"] = "MAX(Banc[Latence p95]) / 1000"
    m["Banc verdict"] = "SELECTEDVALUE(Banc[Décision])"
    m["Couleur de décision"] = (
        f'SWITCH(SELECTEDVALUE(Banc[Code de décision]), "worse", "{ROUGE}", '
        f'"unsafe", "{ROUGE}", "{ANTHRACITE}")')
    m["Format taux"] = (
        "VAR vN = [Documents analysés]\nVAR vSignales = [Nombre de documents signalés]\n"
        f'RETURN IF(vN > 0, IF(vN < {N_MIN}, "n trop faible", FORMAT(DIVIDE(vSignales, vN), "0 %")))')
    m["Mission signalée"] = "VAR v = SUM(Documents[Alertes])\nRETURN IF(v > 0, v)"
    m["Mission documents"] = "IF(NOT ISBLANK([Mission signalée]), COUNTROWS(Documents))"

    formats = {"À traiter inactivité": JOURS, "File attente": JOURS, "File priorité": ENTIER,
               "Banc chiffres": PCT, "Banc attaque": PCT, "Banc latence": '0 "s"'}
    for nom in ("Note Sections acceptées sans retouche", "Note Citations sans source après approbation",
                "Note Citations sans source avant relecture", "Note Phrases vérifiées",
                "H7 citations", "H7 retouche", "Rapport vérifiées", "Rapport détectées"):
        corps = m[nom]
        tete, _, fin = corps.rpartition("RETURN ")
        retour = mesure_reelle(fin, '"Non mesuré"')
        m[nom] = f"{tete}RETURN {retour}" if tete else retour
    return [Mesure(nom, "9. Présentation", dax, formats.get(nom), masquee=True) for nom, dax in m.items()]


def toutes() -> list[Mesure]:
    definitions = {k.nom: k.description for k in KPIS}
    appui = [Mesure(x.nom, x.dossier, x.dax, x.fmt, definitions.get(x.nom, "")) for x in _appui()]
    return appui + presentation()


def kpi_md() -> str:
    dax = {x.nom: x.dax for x in _appui()}
    out = [
        "# Indicateurs du tableau de bord Power BI", "",
        "> Fichier généré par `python bi/pbip/build_pbip.py` depuis [`pbip/indicateurs.py`](pbip/indicateurs.py)",
        "> et [`pilotage.py`](../backend/app/dw/pilotage.py), la source unique des seuils et des règles.",
        "> Qui voit quoi : [docs/14](../docs/14-acteurs-dashboard.md).", "",
        "Principes : au plus 4 indicateurs par page acteur, chacun lié à une décision ; "
        f"un taux va avec son effectif et disparaît sous {N_MIN} cas ; "
        "un critère non mesuré s'affiche « non mesuré », sans verdict. "
        "Sur les données de démonstration, aucune qualité de modèle n'est mesurée.",
    ]
    for acteur in (CONSULTANT, RESPONSABLE, RAPPORT, ADMINISTRATION):
        out += ["", f"## {acteur}"]
        for k in (x for x in KPIS if x.acteur == acteur):
            out += ["", f"### {k.nom}", "", f"- **Décision** : {k.decision}",
                    f"- **Formule** : {k.formule}", f"- **Cible** : {k.cible}", f"- **Portée** : {k.portee}"]
            if k.limite:
                out.append(f"- **Limite** : {k.limite}")
            out += ["", "```dax", f"{k.nom} =", dax[k.nom], "```"]
    out += ["", "## Recommandations", "",
            f"Règles déterministes, sans LLM. Les {pilotage.MAX_RECOMMENDATIONS} plus prioritaires qui se "
            "déclenchent sur le périmètre filtré (client, type, consultant) s'affichent. "
            "Elles décrivent la situation à la date des données et ne suivent pas la période.", "",
            "| Priorité | Code | Pour | Constat | Seuil | Action |", "|---:|---|---|---|---|---|"]
    out += [f"| {r.priority} | `{r.code}` | {r.actor} | {r.label} : n sur N {r.population} | {r.threshold} | {r.action} |"
            for r in pilotage.RULES]
    out += ["", "## Alertes et tuiles", "",
            "Les cartes portent des mesures numériques : dans Power BI Service, elles peuvent être épinglées "
            "et recevoir une alerte (voir [PUBLICATION.md](PUBLICATION.md)).",
            "", "## Prédictions", "",
            "### Charge de relecture des 2 prochaines semaines", "",
            f"- **Méthode** : moyenne des {pilotage.WINDOW_WEEKS} dernières semaines glissantes × 2, "
            "renvois resoumis compris.",
            f"- **Intervalle** : {pilotage.INTERVAL * 100:.0f} %, d'après les erreurs des prévisions rétrospectives. "
            "Leurs fenêtres se chevauchent : l'intervalle est indicatif.",
            "- **Référence naïve** : répéter les 2 dernières semaines.",
            f"- **Publication** : au moins {N_MIN} soumissions et {pilotage.MIN_ORIGINS} prévisions vérifiables, "
            "et une erreur absolue moyenne inférieure à la référence. Sinon « historique insuffisant » "
            "ou « pas de prévision fiable ».", "",
            "### Risque de renvoi d'un livrable en attente", "",
            "- **Méthode** : taux de renvoi observé à la première relecture, selon la présence d'au moins "
            "une phrase bloquante, tous clients du cabinet.",
            f"- **Intervalle** : Wilson à {pilotage.INTERVAL * 100:.0f} %, avec l'effectif du groupe.",
            f"- **Publication** : au moins {pilotage.MIN_RISK_GROUP} cas par groupe, "
            f"{pilotage.MIN_RISK_BACKTEST} cas rétrospectifs et un score de Brier meilleur que le taux global.",
            "- **Ordre de la file** : jours d'attente × (1 + risque de renvoi).", "",
            "## Banc d'essai", "",
            f"Règle de [docs/08 §6](../docs/08-modele-rag-evaluation.md) : une configuration n'est retenue face à "
            f"{pilotage.REFERENCE_CONFIG} que si l'intervalle à 95 % de l'écart de TPV (bootstrap apparié sur les "
            "sections) est au-dessus de 0 et qu'aucune métrique de sécurité ne se dégrade."]
    return "\n".join(out) + "\n"


def measures_dax() -> str:
    out = ["// Mesures du rapport Power BI. GÉNÉRÉ par bi/pbip/build_pbip.py : modifier bi/pbip/indicateurs.py.",
           "// Les noms de tables et de colonnes sont ceux du modèle CadrageIA ; définitions dans bi/KPI.md.", ""]
    for x in toutes():
        if x.masquee:
            continue
        out += [f"// {ligne}" for ligne in x.description.split("\n") if ligne]
        out += [f"{x.nom} =", x.dax, ""]
    return "\n".join(out)
