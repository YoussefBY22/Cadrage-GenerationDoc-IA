"""Indicateurs du rapport Power BI : source unique des mesures, de `bi/measures.dax` et de `bi/KPI.md`.

Trois familles :
- KPIS : les indicateurs de pilotage, chacun défini (formule, intérêt, cible) ;
- APPUI : les comptes et calculs intermédiaires utiles aux visuels ;
- presentation() : les mesures masquées qui écrivent titres, statuts et couleurs selon les filtres.
"""
from __future__ import annotations

from dataclasses import dataclass

# Seuils de l'hypothèse H7 (docs/01-cahier-des-charges.md §13)
CIBLE_REUTILISABLE = 0.50
CIBLE_TEMPS = 0.30
CIBLE_CITATIONS_INVENTEES = 0
REFERENCE = "B"  # configuration de référence du banc d'évaluation (docs/08)

ANTHRACITE, GRIS, GRIS_CLAIR, JAUNE = "#2E2E38", "#747480", "#C4C4CD", "#FFE600"
ROUGE, VERT = "#B4232F", "#1E6B4F"
FOND_ROUGE, FOND_GRIS, FOND_BLANC = "#F6D5D8", "#E9E9EF", "#FFFFFF"

PCT, ENTIER = "0 %", "#,0"
HEURES, SECONDES = '0 "h"', '0 "s"'
POINTS = '+0" pts";-0" pts";"0 pt"'
PAS_DE_SEUIL = "Aucun seuil dans H7 : indicateur de suivi."

QUALITE, PRODUCTIVITE = "1. Qualité et preuves", "2. Productivité et relecture"
MODELES, SECURITE = "3. Comparaison des modèles", "4. Sécurité et usage"


@dataclass(frozen=True)
class Kpi:
    nom: str
    dossier: str
    dax: str
    fmt: str
    formule: str
    pourquoi: str
    cible: str
    limite: str = ""

    @property
    def description(self) -> str:
        texte = f"Formule : {self.formule}\nPourquoi : {self.pourquoi}\nCible : {self.cible}"
        return texte + (f"\nLimite : {self.limite}" if self.limite else "")


@dataclass(frozen=True)
class Mesure:
    nom: str
    dossier: str
    dax: str
    fmt: str | None
    description: str = ""
    masquee: bool = False


KPIS: list[Kpi] = [
    Kpi("Phrases vérifiées", QUALITE,
        "DIVIDE([Nombre de phrases vérifiées], [Phrases générées])", PCT,
        "phrases validées par le vérificateur ÷ phrases des sections générées (TPV, taux de phrases vérifiées).",
        "c'est la promesse du produit : chaque phrase s'appuie sur une preuve du dossier.",
        "au moins 50 %. Ce plancher est déduit de H7 : une phrase non vérifiée n'est pas réutilisable telle quelle.",
        "mesure l'ancrage dans les sources, pas la vérité du contenu."),
    Kpi("Citations inventées", QUALITE,
        "VAR vTotal = SUM('Générations'[Citations produites])\n"
        "RETURN IF(NOT ISBLANK(vTotal), vTotal - SUM('Générations'[Citations valides en nombre]))", ENTIER,
        "citations produites − citations dont la source existe dans le dossier.",
        "une source inexistante ou prise dans un autre dossier ruine la confiance et peut fuiter entre clients.",
        "0 (H7).",
        "compte ce que le modèle a produit et que le vérificateur a signalé, pas ce qui reste après relecture."),
    Kpi("Chiffres retrouvés dans la source", QUALITE,
        "DIVIDE(SUM('Générations'[Chiffres retrouvés]), SUM('Générations'[Chiffres cités]))", PCT,
        "chiffres cités retrouvés dans le passage source ÷ chiffres cités.",
        "un montant, un délai ou un taux faux est l'erreur la plus coûteuse dans un livrable de conseil.",
        PAS_DE_SEUIL,
        "vide si aucun chiffre n'est cité (kpi.py renvoie 1 dans ce cas)."),
    Kpi("Sections refusées faute de preuve", QUALITE,
        "DIVIDE([Nombre de sections refusées], [Générations de sections])", PCT,
        "générations de sections refusées ÷ générations de sections (constats exclus).",
        "un refus vaut mieux qu'une invention ; un taux élevé révèle des dossiers trop pauvres ou une recherche mal réglée.",
        PAS_DE_SEUIL,
        "kpi.py rapporte les refus à toutes les générations, constats compris."),

    Kpi("Temps gagné", PRODUCTIVITE,
        "DIVIDE(\n"
        "    CALCULATE(SUM('Sections approuvées'[Minutes gagnées]), KEEPFILTERS('Sections approuvées'[Refusée] = 0)),\n"
        "    SUM('Sections approuvées'[Minutes de référence]))", PCT,
        "minutes gagnées sur les sections rédigées ÷ minutes d'une rédaction manuelle de toutes les sections approuvées.",
        "c'est le retour sur investissement attendu par le cabinet.",
        "au moins 30 % (H7).",
        "estimation : 30 min par section manuelle (à valider), gain proportionnel au texte conservé, "
        "relecture non déduite. Une section refusée ne fait rien gagner."),
    Kpi("Temps gagné par livrable", PRODUCTIVITE,
        "DIVIDE([Heures gagnées], [Livrables approuvés])", HEURES,
        "heures gagnées ÷ livrables approuvés.",
        "traduit le pourcentage en temps de consultant rendu à l'analyse.",
        "aucun seuil en heures dans H7, qui raisonne en pourcentage (voir Temps gagné).",
        "même estimation que Temps gagné."),
    Kpi("Sections acceptées sans retouche", PRODUCTIVITE,
        "DIVIDE([Nombre de sections sans retouche], [Sections rédigées puis approuvées])", PCT,
        "sections approuvées mot pour mot ÷ sections rédigées puis approuvées (refus exclus).",
        "mesure l'adoption réelle : le consultant garde le texte au lieu de le refaire.",
        "au moins 50 % (H7, « réutilisables telles quelles »).",
        "H7 raisonne par phrase et l'entrepôt par section : une seule retouche disqualifie la section, "
        "la mesure est donc plus sévère que H7."),
    Kpi("Délai de validation", PRODUCTIVITE,
        "MEDIAN(Relectures[Délai en heures])", HEURES,
        "médiane des heures entre la première soumission et l'approbation, par livrable.",
        "le temps gagné à la rédaction est perdu si le livrable attend en relecture.",
        PAS_DE_SEUIL,
        "heures calendaires ; non filtré par modèle, car un livrable peut en mélanger plusieurs."),
    Kpi("Renvois en correction", PRODUCTIVITE,
        "DIVIDE(SUM(Relectures[Renvois]), SUM(Relectures[Soumissions]))", PCT,
        "renvois par le relecteur ÷ soumissions en relecture.",
        "signale des brouillons qui arrivent trop tôt ou trop fragiles chez le manager.",
        PAS_DE_SEUIL,
        "non filtré par modèle."),

    Kpi("Écart à la référence B", MODELES,
        "VAR vTaux = [Phrases vérifiées]\n"
        'VAR vReference = CALCULATE([Phrases vérifiées], REMOVEFILTERS(Configurations), '
        f'Configurations[Configuration] = "{REFERENCE}")\n'
        "RETURN IF(NOT ISBLANK(vTaux) && NOT ISBLANK(vReference), (vTaux - vReference) * 100)", POINTS,
        "(phrases vérifiées de la configuration − celles de la référence B) × 100, en points.",
        "un modèle plus lourd ou affiné ne se justifie que s'il fait mieux que la référence.",
        "supérieur à 0 pour justifier un changement ; H7 ne fixe pas de seuil.",
        "échantillons de tailles différentes : lire avec le nombre de générations."),
    Kpi("Temps de réponse p95", MODELES,
        'CALCULATE(\n'
        '    PERCENTILEX.INC(\'Appels au modèle\', \'Appels au modèle\'[Latence en ms], 0.95) / 1000,\n'
        '    KEEPFILTERS(\'Appels au modèle\'[Nature] = "section"))', SECONDES,
        "95e centile de la durée d'un appel de rédaction de section, en secondes.",
        "au-delà de quelques dizaines de secondes, le consultant cesse d'utiliser l'outil ; "
        "cette mesure arbitre qualité contre vitesse.",
        PAS_DE_SEUIL,
        "appels de section seulement (kpi.py prend tous les appels) ; "
        "la latence d'une tentative répétée est répartie à parts égales."),

    Kpi("Alertes d'injection", SECURITE,
        "IF([Documents analysés] > 0, SUM(Documents[Alertes]) + 0)", ENTIER,
        "somme des consignes cachées détectées dans les documents importés.",
        "un document piégé peut détourner le modèle ; chaque alerte demande un examen humain.",
        "aucun seuil dans H7 ; examiner 100 % des alertes.",
        "compte les détections, pas les attaques réussies ; non filtré par modèle ni par type de livrable."),
    Kpi("Documents signalés", SECURITE,
        "DIVIDE([Nombre de documents signalés] + 0, [Documents analysés])", PCT,
        "documents avec au moins une alerte ÷ documents importés.",
        "situe le risque : incident isolé ou source documentaire à revoir.",
        PAS_DE_SEUIL,
        "un document est daté de la première génération de sa mission."),
    Kpi("Livrables approuvés", SECURITE,
        "DISTINCTCOUNT('Sections approuvées'[Identifiant du livrable])", ENTIER,
        "nombre de livrables distincts approuvés par un manager.",
        "c'est l'usage qui compte : un brouillon non approuvé ne crée pas de valeur.",
        PAS_DE_SEUIL),
]

_SECTIONS = "KEEPFILTERS('Générations'[Nature] = \"Section\")"
_REDIGEE = "KEEPFILTERS('Sections approuvées'[Refusée] = 0)"
_SUMMARIZE = ("SUMMARIZE('Générations', 'Générations'[Clé de mission], 'Générations'[Code du type], "
              "'Générations'[Code de section])")

APPUI: list[Mesure] = [
    Mesure("Phrases générées", QUALITE,
           "CALCULATE(SUM('Générations'[Phrases produites]), KEEPFILTERS('Générations'[Statut] = \"ok\"))", ENTIER,
           "Phrases des générations réussies."),
    Mesure("Nombre de phrases vérifiées", QUALITE,
           "CALCULATE(SUM('Générations'[Phrases validées]), KEEPFILTERS('Générations'[Statut] = \"ok\"))", ENTIER,
           "Phrases validées par le vérificateur."),
    Mesure("Phrases à vérifier", QUALITE,
           "CALCULATE(SUM('Générations'[Phrases en avertissement]), KEEPFILTERS('Générations'[Statut] = \"ok\"))", ENTIER,
           "Phrases en avertissement, à relire."),
    Mesure("Phrases rejetées", QUALITE,
           "CALCULATE(SUM('Générations'[Phrases en échec]), KEEPFILTERS('Générations'[Statut] = \"ok\"))", ENTIER,
           "Phrases bloquées par le vérificateur."),
    Mesure("Variation de phrases", QUALITE,
           "SWITCH(SELECTEDVALUE(Cascade[Ordre]), 1, [Phrases générées], 2, -[Phrases à vérifier], 3, -[Phrases rejetées],\n"
           "    [Phrases générées] - [Phrases à vérifier] - [Phrases rejetées])", ENTIER,
           "Contribution de chaque marche de la cascade, des phrases générées aux phrases vérifiées."),
    Mesure("Anomalies", QUALITE,
           "CALCULATE(COUNTROWS(Citations), KEEPFILTERS(Citations[Code de contrôle] <> \"NONE\"))", ENTIER,
           "Contrôles de citation en anomalie."),
    Mesure("Générations de sections", QUALITE,
           f"CALCULATE(COUNTROWS('Générations'), {_SECTIONS})", ENTIER,
           "Tentatives de rédaction d'une section, constats exclus."),
    Mesure("Nombre de sections refusées", QUALITE,
           f"CALCULATE(COUNTROWS('Générations'), {_SECTIONS}, KEEPFILTERS('Générations'[Statut] = \"refused\")) + 0", ENTIER,
           "Générations de sections refusées faute de preuve."),

    Mesure("Sections demandées", PRODUCTIVITE,
           f"CALCULATE(COUNTROWS({_SUMMARIZE}), {_SECTIONS})", ENTIER,
           "Sections distinctes demandées (mission, type de livrable, section)."),
    Mesure("Sections rédigées", PRODUCTIVITE,
           f"CALCULATE(COUNTROWS({_SUMMARIZE}), {_SECTIONS}, KEEPFILTERS('Générations'[Statut] = \"ok\"))", ENTIER,
           "Sections distinctes rédigées au moins une fois."),
    Mesure("Sections rédigées puis approuvées", PRODUCTIVITE,
           f"CALCULATE(COUNTROWS('Sections approuvées'), {_REDIGEE})", ENTIER,
           "Sections approuvées, refus exclus."),
    Mesure("Nombre de sections sans retouche", PRODUCTIVITE,
           "VAR vRedigees = [Sections rédigées puis approuvées]\n"
           f"RETURN IF(vRedigees > 0, CALCULATE(COUNTROWS('Sections approuvées'), {_REDIGEE},\n"
           "    KEEPFILTERS('Sections approuvées'[Sans retouche] = 1)) + 0)", ENTIER,
           "Sections approuvées mot pour mot."),
    Mesure("Sections à l'étape", PRODUCTIVITE,
           "SWITCH(SELECTEDVALUE('Étapes'[Ordre]), 1, [Sections demandées], 2, [Sections rédigées],\n"
           "    3, [Sections rédigées puis approuvées], 4, [Nombre de sections sans retouche])", ENTIER,
           "Volume à chaque étape de l'entonnoir, chacune à sa propre date."),
    Mesure("Heures gagnées", PRODUCTIVITE,
           f"CALCULATE(SUM('Sections approuvées'[Minutes gagnées]), {_REDIGEE}) / 60", HEURES,
           "Minutes gagnées estimées ÷ 60, refus exclus."),
    Mesure("Part réécrite", PRODUCTIVITE,
           f"CALCULATE(AVERAGE('Sections approuvées'[Part de texte modifiée]), {_REDIGEE})", PCT,
           "Part moyenne du texte modifiée avant approbation, refus exclus."),

    Mesure("Citations valides", MODELES,
           "DIVIDE(SUM('Générations'[Citations valides en nombre]), SUM('Générations'[Citations produites]))", PCT,
           "Citations dont la source existe dans le dossier ÷ citations produites."),
    Mesure("Valeur du critère", MODELES,
           "SWITCH(SELECTEDVALUE('Critères'[Ordre]), 1, [Phrases vérifiées], 2, [Citations valides],\n"
           "    3, [Chiffres retrouvés dans la source], 4, [Sections acceptées sans retouche])", PCT,
           "Valeur du critère affiché dans chaque petit multiple."),

    Mesure("Documents analysés", SECURITE, "COUNTROWS(Documents)", ENTIER, "Documents importés."),
    Mesure("Nombre de documents signalés", SECURITE,
           "CALCULATE(COUNTROWS(Documents), KEEPFILTERS(Documents[Alertes] > 0))", ENTIER,
           "Documents avec au moins une alerte."),
    Mesure("Documents sans alerte", SECURITE,
           "CALCULATE(COUNTROWS(Documents), KEEPFILTERS(Documents[Alertes] = 0))", ENTIER,
           "Documents sans alerte."),
    Mesure("Alertes par mission", SECURITE,
           "CALCULATE(SUM(Documents[Alertes]), KEEPFILTERS(Documents[Alertes] > 0))", ENTIER,
           "Alertes, missions sans alerte masquées."),
    Mesure("Missions actives", SECURITE, "DISTINCTCOUNT('Générations'[Clé de mission])", ENTIER,
           "Missions avec au moins une génération."),
    Mesure("Générations", SECURITE, "COUNTROWS('Générations')", ENTIER,
           "Appels de génération, sections et constats."),
]


def _valeur(nom: str, fmt: str) -> str:
    """Valeur de carte en texte : virgule décimale française, quelle que soit la langue de Power BI Desktop."""
    return f'VAR v = [{nom}]\nRETURN IF(ISBLANK(v), "—", FORMAT(v, "{fmt}", "fr-FR"))'


def _statut(nom: str, test: str, atteint: str, manque: str) -> str:
    return (f'VAR v = [{nom}]\nRETURN IF(ISBLANK(v), "Aucune donnée", '
            f'IF(v {test}, "✓ {atteint}", "✕ {manque}"))')


def _couleur(nom: str, test: str) -> str:
    return f'VAR v = [{nom}]\nRETURN IF(ISBLANK(v), "{GRIS}", IF(v {test}, "{VERT}", "{ROUGE}"))'


def _premier(colonne: str, mesure: str, ordre: str) -> str:
    """Lignes DAX communes : le premier élément de `colonne` selon `mesure`, départage alphabétique."""
    return (f'VAR vListe = FILTER(ADDCOLUMNS(ALLSELECTED({colonne}), "@v", [{mesure}]), NOT ISBLANK([@v]))\n'
            f"VAR vPremier = TOPN(1, vListe, [@v], {ordre}, {colonne}, ASC)\n"
            f"VAR vNom = MAXX(vPremier, {colonne})\n"
            "VAR vValeur = MAXX(vPremier, [@v])\n")


def presentation() -> list[Mesure]:
    m: dict[str, str] = {}

    valeurs = {
        "Phrases vérifiées": "0 %", "Citations inventées": "#,0", "Chiffres retrouvés dans la source": "0 %",
        "Sections refusées faute de preuve": "0 %", "Temps gagné": "0 %",
        "Temps gagné par livrable": "0.0 h", "Sections acceptées sans retouche": "0 %",
        "Délai de validation": "0.0 h", "Renvois en correction": "0 %", "Alertes d'injection": "#,0",
        "Documents signalés": "0 %", "Missions actives": "#,0", "Livrables approuvés": "#,0",
    }
    for nom, fmt in valeurs.items():
        m[f"Carte {nom}"] = _valeur(nom, fmt)

    reutilisable, temps = f"{CIBLE_REUTILISABLE:.0%}"[:-1], f"{CIBLE_TEMPS:.0%}"[:-1]
    seuils = [
        ("Phrases vérifiées", f">= {CIBLE_REUTILISABLE}",
         f"Au-dessus du plancher de {reutilisable} %", f"Sous le plancher de {reutilisable} %"),
        ("Citations inventées", f"<= {CIBLE_CITATIONS_INVENTEES}",
         f"Cible atteinte : {CIBLE_CITATIONS_INVENTEES}", f"Cible : {CIBLE_CITATIONS_INVENTEES}"),
        ("Sections acceptées sans retouche", f">= {CIBLE_REUTILISABLE}",
         f"Cible atteinte : ≥ {reutilisable} %", f"Cible : ≥ {reutilisable} %"),
        ("Temps gagné", f">= {CIBLE_TEMPS}",
         f"Cible atteinte : ≥ {temps} %", f"Cible : ≥ {temps} %"),
    ]
    for nom, test, atteint, manque in seuils:
        m[f"Statut {nom}"] = _statut(nom, test, atteint, manque)
        m[f"Couleur {nom}"] = _couleur(nom, test)

    m["Bandeau données"] = (
        'IF(CALCULATE(MAX(Missions[Est une démonstration]), REMOVEFILTERS()) = 1,\n'
        '    "Données de démonstration · valeurs inventées", " ")')
    m["Verdict"] = (
        f"VAR vCitations = [Citations inventées]\nVAR vRetouche = [Sections acceptées sans retouche]\n"
        "VAR vTemps = [Temps gagné]\n"
        f"VAR vAtteints = IF(NOT ISBLANK(vCitations) && vCitations <= {CIBLE_CITATIONS_INVENTEES}, 1, 0)\n"
        f"    + IF(vRetouche >= {CIBLE_REUTILISABLE}, 1, 0) + IF(vTemps >= {CIBLE_TEMPS}, 1, 0)\n"
        'RETURN IF(ISBLANK(vCitations) || ISBLANK(vRetouche) || ISBLANK(vTemps),\n'
        '    "Pas assez de données dans cette sélection pour conclure",\n'
        '    vAtteints & IF(vAtteints > 1, " critères atteints", " critère atteint") & " sur 3")')
    m["Détail du verdict"] = (
        f"VAR vCitations = [Citations inventées]\nVAR vRetouche = [Sections acceptées sans retouche]\n"
        "VAR vTemps = [Temps gagné]\n"
        "RETURN IF(ISBLANK(vCitations) || ISBLANK(vRetouche) || ISBLANK(vTemps), \" \",\n"
        f'    IF(vTemps >= {CIBLE_TEMPS}, "✓", "✕") & " Temps gagné  ·  "\n'
        f'    & IF(vRetouche >= {CIBLE_REUTILISABLE}, "✓", "✕") & " Texte réutilisable  ·  "\n'
        f'    & IF(vCitations <= {CIBLE_CITATIONS_INVENTEES}, "✓", "✕") & " Zéro citation inventée")')

    m["Tuile qualité"] = (
        "VAR vTotal = [Phrases générées]\n"
        'RETURN IF(ISBLANK(vTotal), "—", FORMAT(vTotal - [Nombre de phrases vérifiées], "#,0", "fr-FR") & " phrases à revoir")')
    m["Tuile productivité"] = (
        "VAR v = [Heures gagnées]\n"
        'RETURN IF(ISBLANK(v), "—", FORMAT(v, "#,0", "fr-FR") & " h gagnées")')
    m["Tuile modèles"] = (
        _premier("Configurations[Configuration]", "Phrases vérifiées", "DESC")
        + 'RETURN IF(ISBLANK(vNom), "—", vNom & " en tête à " & FORMAT(vValeur, "0 %"))')
    m["Tuile sécurité"] = (
        "VAR v = [Alertes d'injection]\n"
        'RETURN IF(ISBLANK(v), "—", v & IF(v > 1, " alertes", " alerte"))')

    m["Titre cascade"] = (
        "VAR vTotal = [Phrases générées]\nVAR vOk = [Nombre de phrases vérifiées] + 0\n"
        'RETURN IF(ISBLANK(vTotal), "Aucune phrase générée dans cette sélection",\n'
        '    vOk & " phrases sur " & vTotal & " sont vérifiées")')
    m["Titre anomalies"] = (
        _premier("Citations[Anomalie]", "Anomalies", "DESC")
        + 'RETURN IF(ISBLANK(vNom), "Aucune anomalie dans cette sélection",\n'
          '    "« " & vNom & " » est la première anomalie (" & vValeur & " cas)")')
    m["Titre sections fragiles"] = (
        _premier("'Générations'[Section]", "Phrases vérifiées", "ASC")
        + 'RETURN IF(ISBLANK(vNom), "Aucune section rédigée dans cette sélection",\n'
          '    "« " & vNom & " » est la section la moins vérifiée (" & FORMAT(vValeur, "0 %") & ")")')
    m["Titre entonnoir"] = (
        "VAR vDebut = [Sections demandées]\nVAR vFin = [Nombre de sections sans retouche]\n"
        'RETURN IF(ISBLANK(vDebut) || ISBLANK(vFin), "Des sections demandées aux sections réutilisées",\n'
        '    vFin & " sections sur " & vDebut & " vont au bout sans retouche")')
    m["Titre retouches"] = (
        "VAR vTotal = [Sections rédigées puis approuvées]\n"
        "VAR vModifiees = vTotal - [Nombre de sections sans retouche]\n"
        'RETURN IF(ISBLANK(vTotal), "Aucune section approuvée dans cette sélection",\n'
        '    vModifiees & " sections approuvées sur " & vTotal & " ont été retouchées")')
    m["Titre réécriture"] = (
        _premier("'Sections approuvées'[Section]", "Part réécrite", "DESC")
        + 'RETURN IF(ISBLANK(vNom), "Aucune section approuvée dans cette sélection",\n'
          '    "« " & vNom & " » demande le plus de réécriture")')
    m["Titre critères"] = (
        _premier("Configurations[Configuration]", "Phrases vérifiées", "DESC")
        + 'RETURN IF(ISBLANK(vNom), "Aucune configuration à comparer",\n'
          '    "La configuration " & vNom & " vérifie le plus de phrases (" & FORMAT(vValeur, "0 %") & ")")')
    m["Titre bilan"] = (
        _premier("Configurations[Configuration et modèle]", "Écart à la référence B", "DESC")
        + 'RETURN IF(ISBLANK(vNom), "Bilan de chaque configuration",\n'
          '    IF(ROUND(vValeur, 0) > 0,\n'
          '        LEFT(vNom, 1) & " devance la référence B de " & FORMAT(vValeur, "0") & " points",\n'
          '        "Aucune configuration ne devance la référence B"))')
    m["Titre arbitrage"] = (
        'VAR vListe = FILTER(ADDCOLUMNS(ALLSELECTED(Configurations[Configuration]), "@q", [Phrases vérifiées],\n'
        '    "@t", [Temps de réponse p95]), NOT ISBLANK([@q]) && NOT ISBLANK([@t]))\n'
        "VAR vFiable = MAXX(TOPN(1, vListe, [@q], DESC, Configurations[Configuration], ASC), Configurations[Configuration])\n"
        "VAR vRapide = MAXX(TOPN(1, vListe, [@t], ASC, Configurations[Configuration], ASC), Configurations[Configuration])\n"
        'RETURN IF(ISBLANK(vFiable), "Qualité et vitesse",\n'
        '    IF(vFiable = vRapide, vFiable & " est la plus fiable et la plus rapide",\n'
        '        vFiable & " est la plus fiable, " & vRapide & " la plus rapide"))')
    m["Titre alertes"] = (
        "VAR vAlertes = [Alertes d'injection] + 0\n"
        "VAR vMissions = CALCULATE(DISTINCTCOUNT(Documents[Clé de mission]), KEEPFILTERS(Documents[Alertes] > 0))\n"
        'RETURN IF(vAlertes = 0, "Aucune alerte d\'injection dans cette sélection",\n'
        '    vAlertes & IF(vAlertes > 1, " alertes réparties sur ", " alerte sur ")\n'
        '    & vMissions & IF(vMissions > 1, " missions", " mission") & " à examiner")')
    m["Titre formats"] = (
        _premier("Documents[Format]", "Nombre de documents signalés", "DESC")
        + 'RETURN IF(ISBLANK(vNom), "Aucun format de document signalé",\n'
          '    IF(COUNTROWS(FILTER(vListe, [@v] = vValeur)) > 1, "Plusieurs formats sont touchés à égalité",\n'
          '        vNom & " est le format le plus souvent signalé"))')
    m["Titre usage"] = (
        "VAR vTotal = [Générations] + 0\nVAR vClients = DISTINCTCOUNT('Générations'[Client d'origine])\n"
        'RETURN IF(vTotal = 0, "Aucune génération dans cette sélection",\n'
        '    vTotal & " générations pour " & vClients & IF(vClients > 1, " clients", " client"))')

    m["Fond de taux"] = (
        "VAR v = [Phrases vérifiées]\n"
        f'RETURN IF(NOT ISBLANK(v), SWITCH(TRUE(), v < {CIBLE_REUTILISABLE}, "{FOND_ROUGE}", '
        f'v >= 0.8, "{FOND_BLANC}", "{FOND_GRIS}"))')
    m["Couleur d'écart"] = (
        "VAR v = ROUND([Écart à la référence B], 0)\n"
        f'RETURN SWITCH(TRUE(), v > 0, "{VERT}", v < 0, "{ROUGE}", "{ANTHRACITE}")')
    m["Couleur du critère"] = (
        "VAR v = [Valeur du critère]\n"
        "VAR vMax = MAXX(ALLSELECTED(Configurations[Configuration]), [Valeur du critère])\n"
        f'RETURN IF(ROUND(v, 2) = ROUND(vMax, 2), "{JAUNE}", "{GRIS_CLAIR}")')
    m["Couleur de réécriture"] = (
        "VAR v = [Part réécrite]\n"
        "VAR vMax = MAXX(ALLSELECTED('Sections approuvées'[Section]), [Part réécrite])\n"
        f'RETURN IF(v = vMax, "{JAUNE}", "{GRIS_CLAIR}")')
    m["Couleur de retouche"] = (
        f'IF(SELECTEDVALUE(\'Sections approuvées\'[Ordre de retouche]) = 1, "{JAUNE}", "{GRIS_CLAIR}")')

    return [Mesure(nom, "9. Présentation", dax, None, masquee=True) for nom, dax in m.items()]


def toutes() -> list[Mesure]:
    definis = [Mesure(k.nom, k.dossier, k.dax, k.fmt, k.description) for k in KPIS]
    return definis + APPUI + presentation()


def kpi_md() -> str:
    out = [
        "# Indicateurs du tableau de bord Power BI",
        "",
        "> Fichier généré par `python bi/pbip/build_pbip.py` depuis [`pbip/indicateurs.py`](pbip/indicateurs.py).",
        "> La même définition figure dans la description de chaque mesure (info-bulle du volet Données)",
        "> et dans l'icône d'information des cartes du rapport.",
        "",
        "## Critères de réussite (hypothèse H7)",
        "",
        "Source : [cahier des charges](../docs/01-cahier-des-charges.md), §13. "
        "H7 est une hypothèse de travail, à valider avec l'entreprise.",
        "",
        "| Critère H7 | Indicateur du rapport | Cible |",
        "|---|---|---|",
        f"| 0 citation inventée | Citations inventées | {CIBLE_CITATIONS_INVENTEES} |",
        f"| Phrases réutilisables telles quelles | Sections acceptées sans retouche (approximation plus sévère) | "
        f"≥ {round(CIBLE_REUTILISABLE * 100)} % |",
        f"| Temps gagné sur la rédaction | Temps gagné (estimation) | ≥ {round(CIBLE_TEMPS * 100)} % |",
        "",
        "Le verdict de la page d'accueil porte sur ces trois critères. Les autres indicateurs expliquent "
        "le résultat et n'ont pas de seuil, sauf le plancher des phrases vérifiées, déduit de H7. "
        "Le palier de 80 % qui colore la matrice est un repère de lecture, pas une cible.",
    ]
    for titre in (QUALITE, PRODUCTIVITE, MODELES, SECURITE):
        out += ["", f"## {titre}"]
        for k in KPIS:
            if k.dossier != titre:
                continue
            out += ["", f"### {k.nom}", "",
                    f"- **Formule** : {k.formule}",
                    f"- **Pourquoi** : {k.pourquoi}",
                    f"- **Cible** : {k.cible}"]
            if k.limite:
                out.append(f"- **Limite** : {k.limite}")
            out += ["", "```dax", f"{k.nom} =", k.dax, "```"]
    out += [
        "",
        "## Écarts volontaires avec `backend/app/dw/kpi.py`",
        "",
        "- **Sections refusées** : l'entrepôt les enregistre « inchangées », avec 30 minutes gagnées chacune "
        "(0 mot généré, 0 mot final). Le rapport les exclut des sections sans retouche et du temps gagné. "
        "`kpi.unchanged_rate` et `kpi.minutes_saved` les comptent encore et donnent donc des valeurs plus flatteuses.",
        "- **Taux de refus** : rapporté aux générations de sections, constats exclus.",
        "- **Temps de réponse p95** : calculé sur les appels de section, pour comparer des tâches identiques.",
        "- **Chiffres retrouvés** : vide, et non 100 %, quand aucun chiffre n'est cité.",
        "",
        "Le taux de phrases vérifiées, les citations valides, le délai de validation, les renvois en correction "
        "et les alertes d'injection suivent les mêmes formules que `kpi.py`.",
    ]
    return "\n".join(out) + "\n"


def measures_dax() -> str:
    out = ["// Mesures du rapport Power BI. GÉNÉRÉ par bi/pbip/build_pbip.py : modifier bi/pbip/indicateurs.py.",
           "// Les noms de tables et de colonnes sont ceux du modèle CadrageIA ; définitions dans bi/KPI.md.", ""]
    for m in toutes():
        if m.masquee:
            continue
        out += [f"// {ligne}" for ligne in m.description.split("\n")]
        out += [f"{m.nom} =", m.dax, ""]
    return "\n".join(out)
