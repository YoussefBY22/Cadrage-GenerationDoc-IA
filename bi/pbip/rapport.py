"""Rapport PBIR : quatre pages d'analyse et une page imprimable, pour décider.

Règles de conception (docs/14 §6) :
- chaque page porte au moins un vrai graphique (courbe, barres, anneau, matrice colorée) et des info-bulles ;
- aucune clé technique : libellés lisibles, rôle de chaque section dans son info-bulle ;
- tout visuel qui mélange projets réels et de démonstration le dit dans son sous-titre ([DÉMO]) ;
- filtres synchronisés sur toutes les pages : données, plage de dates (au jour), mois, projet, client,
  consultant, type de livrable ;
- texte alternatif sur ce qui porte une information, décor hors de l'ordre de tabulation.

Grille 1600 × 900 (page imprimable : 900 × 1273, A4 portrait) : barre latérale de 256 px,
contenu de 288 à 1568 px, gouttière de 16 px.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from indicateurs import (
    ANTHRACITE,
    GRIS,
    GRIS_CLAIR,
    GRIS_TEXTE,
    JAUNE,
    ROUGE,
    SOUS_TITRES,
    TOUS,
    TOUS_MOIS,
    TOUTES_DONNEES,
)
from pbir import CHAQUE_POINT, DEFAUT, SCHEMA, SCHEMA_VISUEL, SEMIBOLD, categorie, col, mes, props, ref, requete, serie

L, H, BARRE = 1600, 900, 256
A4_L, A4_H = 900, 1273
X0, LC, G = 288, 1280, 16
BAS = H - 24
BLANC, FOND, BARRE_2 = "#FFFFFF", "#F6F6FA", "#3C3C48"
THEME_BASE = "CY26SU02"
TITRE_VISUEL = 13.0
MAX_ALT = 250  # limite de Power BI pour un texte alternatif

PAGES = {"synthese": "Synthèse", "projet": "Projet", "qualite": "Qualité de l'IA", "entrainement": "Entraînement",
         "impression": "Rapport imprimable"}
VISIBLES = ("synthese", "projet", "qualite", "entrainement")
MASQUEES = ("impression",)
SEGMENTS = {  # groupe de synchronisation → (libellé, table, colonne, valeur par défaut)
    "donnees": ("Données", "Choix des données", "Données choisies", TOUTES_DONNEES),
    "periode": ("Période (au jour)", "Calendrier", "Date", None),
    "mois": ("Mois", "Choix du mois", "Mois choisi", TOUS_MOIS),
    "projet": ("Projet", "Choix du projet", "Projet choisi", TOUS),
    "client": ("Client", "Choix du client", "Client choisi", TOUS),
    "consultant": ("Consultant", "Choix du consultant", "Consultant choisi", TOUS),
    "type": ("Type de livrable", "Choix du type", "Type choisi", TOUS),
}
HAUTEUR_SEGMENT = {"periode": 86}
FICHE = 560
PROJET_PAR_DEFAUT = {"valeur": TOUS}  # projet affiché sur la page Projet : le projet réel, lu dans l'export
RESPONSIVES = ("barChart", "clusteredBarChart", "clusteredColumnChart", "columnChart", "lineChart",
               "hundredPercentStackedBarChart", "donutChart")

# Couleurs par valeur : la même partout (charte : rouge réservé à ce qui demande une action)
COULEURS_ETAT = {"Brouillon": GRIS_CLAIR, "En relecture": JAUNE, "Approuvé": ANTHRACITE, "Renvoyé": ROUGE}
COULEURS_GRAVITE = {"Élevée": ANTHRACITE, "Moyenne": GRIS, "Faible": GRIS_CLAIR}
COULEURS_RESULTAT = {"Réussi": ANTHRACITE, "Refus voulu (preuve insuffisante)": GRIS_CLAIR,
                     "Réussi, avec phrase ou citation fautive": "#E08A93", "Sortie invalide": ROUGE}
COULEURS_MODELE = {"Modèle de base": GRIS_CLAIR, "Essai 1": GRIS, "v4 (adopté)": JAUNE, "v5": ANTHRACITE}
COULEURS_VAGUE = {"Vague 1": JAUNE, "Vague 2": GRIS, "Vague 3": GRIS_CLAIR}
COULEURS_ESSAI = {"Essai 1": GRIS, "v4": JAUNE, "v5": ANTHRACITE}


def colonnes(n: int, largeur: float = LC, x0: float = X0) -> list[tuple[float, float]]:
    """n colonnes égales séparées par la gouttière : [(x, largeur), …]."""
    w = (largeur - G * (n - 1)) / n
    return [(x0 + i * (w + G), w) for i in range(n)]


def alternatif(texte) -> dict:
    return {"general": [props(altText=texte[:MAX_ALT] if isinstance(texte, str) else texte)]}


def selection(table: str, colonne: str, valeur: str) -> dict:
    """Sélection enregistrée d'un segment."""
    litteral = "'" + valeur.replace("'", "''") + "'"
    return {"properties": {"filter": {"filter": {
        "Version": 2, "From": [{"Name": "c", "Entity": table, "Type": 0}],
        "Where": [{"Condition": {"In": {
            "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": colonne}}],
            "Values": [[{"Literal": {"Value": litteral}}]]}}}]}}}}


def couleurs(champ: dict, table: dict[str, str]) -> list:
    return [props(categorie(champ, valeur), fill=c) for valeur, c in table.items()]


def axe(titre: str | None = None, **kw) -> list:
    base = {"show": True, "showAxisTitle": bool(titre), "fontSize": 10.0, "labelColor": ANTHRACITE, **kw}
    if titre:
        base.update(titleText=titre, titleFontSize=10.0, titleColor=GRIS_TEXTE)
    return [props(**base)]


def sans_axe(**kw) -> list:
    return [props(show=False, showAxisTitle=False, gridlineShow=False, **kw)]


def legende(position: str = "Top") -> list:
    return [props(show=True, position=position, showTitle=False, fontSize=10.0, labelColor=ANTHRACITE)]


def etiquettes(**kw) -> list:
    return [props(**{"show": True, "fontSize": 9.5, "color": ANTHRACITE, **kw})]


class Page:
    def __init__(self, pid: str, largeur: int = L, hauteur: int = H, barre: bool = True):
        self.id, self.titre = pid, PAGES[pid]
        self.largeur, self.hauteur = largeur, hauteur
        self.visuels: list[dict] = []
        if barre:
            self.barre_laterale()

    # ------------------------------------------------------------ primitives
    def poser(self, nom: str, vtype: str, boite: tuple, *, req: dict | None = None, objets: dict | None = None,
              conteneur: dict | None = None, synchro: str | None = None, masque: bool = False,
              decor: bool = False, filtres: list | None = None) -> None:
        x, y, w, h = boite
        rang = len(self.visuels)
        visuel: dict = {"visualType": vtype, "drillFilterOtherVisuals": True}
        if req:
            visuel["query"] = req
        if objets:
            visuel["objects"] = objets
        if conteneur:
            visuel["visualContainerObjects"] = conteneur
        if synchro:
            visuel["syncGroup"] = {"groupName": synchro, "fieldChanges": True, "filterChanges": True}
        ordre = -(rang + 1) if decor or masque else rang * 100
        objet = {"$schema": SCHEMA_VISUEL, "name": f"{self.id}_{nom}",
                 "position": {"x": round(x, 2), "y": round(y, 2), "z": rang * 100, "width": round(w, 2),
                              "height": round(h, 2), "tabOrder": ordre},
                 "visual": visuel}
        if filtres:
            objet["filterConfig"] = {"filters": filtres}
        if masque:
            objet["isHidden"] = True
        self.visuels.append(objet)

    @staticmethod
    def nu(**autres) -> dict:
        base = {"background": [props(show=False)], "title": [props(show=False)], "border": [props(show=False)],
                "visualHeader": [props(show=False)],
                "padding": [props(top=0.0, bottom=0.0, left=0.0, right=0.0)]}
        return {**base, **autres}

    def rectangle(self, nom: str, boite: tuple, fond: str, bord: str | None = None) -> None:
        contour = [props(show=False)] if not bord else [props(show=True), props(DEFAUT, lineColor=bord, weight=1.0)]
        self.poser(nom, "shape", boite, decor=True, conteneur=self.nu(), objets={
            "shape": [props(tileShape="rectangle")],
            "fill": [props(show=True), props(DEFAUT, fillColor=fond, transparency=0.0)],
            "outline": contour})

    def texte(self, nom: str, boite: tuple, texte: str, taille: float, encre: str, gras: bool = False,
              alignement: str = "left", vertical: str = "middle", decor: bool = False) -> None:
        conteneur = self.nu() if decor else self.nu(**alternatif(texte))
        self.poser(nom, "shape", boite, decor=decor, conteneur=conteneur, objets={
            "shape": [props(tileShape="rectangle")], "fill": [props(show=False)], "outline": [props(show=False)],
            "text": [props(show=True), props(
                DEFAUT, text=texte, fontSize=float(taille), fontColor=encre,
                fontFamily=SEMIBOLD if gras else "Segoe UI", horizontalAlignment=alignement,
                verticalAlignment=vertical, leftMargin=0, rightMargin=0, topMargin=0, bottomMargin=0)]})

    def calcule(self, nom: str, boite: tuple, titre, taille: float, encre: str, *, gras: bool = False,
                sous_titre=None, taille_sous: float = 10.5, encre_sous: str = GRIS_TEXTE, fond: str | None = None,
                marge: float = 0.0, alignement: str = "left") -> None:
        """Texte calculé par une mesure : porté par le titre (et le sous-titre) d'une forme vide."""
        autres = {"title": [props(show=True, text=titre, fontSize=float(taille), fontColor=encre, titleWrap=True,
                                  fontFamily=SEMIBOLD if gras else "Segoe UI", alignment=alignement)],
                  "padding": [props(top=float(marge), bottom=0.0, left=float(marge), right=float(marge) / 2)],
                  **alternatif(titre)}
        if sous_titre is not None:
            autres["subTitle"] = [props(show=True, text=sous_titre, fontSize=float(taille_sous),
                                        fontColor=encre_sous, titleWrap=True, alignment=alignement)]
            autres["spacing"] = [props(customizeSpacing=True, spaceBelowTitle=6.0)]
        if fond:
            autres["background"] = [props(show=True, color=fond, transparency=0.0)]
        self.poser(nom, "shape", boite, conteneur=self.nu(**autres), objets={
            "shape": [props(tileShape="rectangle")], "fill": [props(show=False)], "outline": [props(show=False)]})

    def bouton(self, nom: str, boite: tuple, texte: str, cible: str, fond: str, encre: str, survol: str,
               gras: bool = False, taille: float = 12.0, alignement: str = "left", bord: str | None = None) -> None:
        marge = 20 if alignement == "left" else 0
        contour = [props(show=bool(bord))]
        if bord:
            contour.append(props(DEFAUT, lineColor=bord, weight=1.0, transparency=0.0))
        self.poser(nom, "actionButton", boite, objets={
            "icon": [props(show=False), props(DEFAUT, shapeType="blank")],
            "outline": contour,
            "fill": [props(show=True), props(DEFAUT, fillColor=fond, transparency=0.0),
                     props({"id": "hover"}, fillColor=survol, transparency=0.0)],
            "text": [props(show=True), props(
                DEFAUT, text=texte, fontColor=encre, fontSize=taille, fontFamily=SEMIBOLD if gras else "Segoe UI",
                horizontalAlignment=alignement, verticalAlignment="middle", leftMargin=marge, rightMargin=0)],
        }, conteneur=self.nu(**alternatif(f"Aller à la page {PAGES[cible]}"), visualLink=[props(
            show=True, type="PageNavigation", navigationSection=cible, tooltip=f"Aller à : {PAGES[cible]}")]))

    def segment(self, groupe: str, boite: tuple, masque: bool = False, synchro: str | None = None,
                libelle: str | None = None, defaut: str | None = None) -> None:
        nom, table, colonne, valeur = SEGMENTS[groupe]
        libelle, defaut = libelle or nom, defaut or valeur
        champ = col(table, colonne)
        objets = {
            "header": [props(show=True, text=libelle, fontColor=JAUNE if groupe == "donnees" else BLANC, textSize=10.5,
                             fontFamily=SEMIBOLD)],
            "items": [props(fontColor=BLANC, background=BARRE_2, textSize=10.5)],
        }
        if defaut is None:  # plage de dates : deux dates et un curseur
            objets["data"] = [props(mode="Between")]
            objets["date"] = [props(fontColor=BLANC, background=BARRE_2, textSize=10.0)]
            objets["slider"] = [props(show=True, color=JAUNE)]
        else:
            objets["data"] = [props(mode="Dropdown")]
            objets["general"] = [selection(table, colonne, defaut)]
            objets["selection"] = [props(selectAllCheckboxEnabled=False, singleSelect=True, strictSingleSelect=True)]
        self.poser(f"segment_{groupe}", "slicer", boite, req=requete({"Values": [champ]}), synchro=synchro or groupe,
                   masque=masque, objets=objets,
                   conteneur={"background": [props(show=False)], "title": [props(show=False)],
                              "visualHeader": [props(show=False)], "border": [props(show=False)],
                              "padding": [props(top=1.0, bottom=1.0, left=4.0, right=4.0)],
                              **alternatif(f"Filtre {libelle}, synchronisé sur toutes les pages")})

    # ------------------------------------------------------------ éléments communs
    def barre_laterale(self) -> None:
        self.rectangle("barre", (0, 0, BARRE, H), ANTHRACITE)
        self.rectangle("logo_carre", (24, 24, 28, 28), JAUNE)
        self.texte("logo_mot", (62, 14, 180, 46), "Cadrage", 21, BLANC, gras=True, decor=True)
        self.texte("logo_legende", (24, 60, 220, 22), "Tableau de bord de décision", 10, GRIS_CLAIR, decor=True)
        for i, pid in enumerate(VISIBLES):
            active = pid == self.id
            self.bouton(f"nav_{pid}", (0, 94 + i * 38, BARRE, 36), PAGES[pid], pid,
                        fond=JAUNE if active else ANTHRACITE, encre=ANTHRACITE if active else BLANC,
                        survol=JAUNE if active else BARRE_2, gras=active)
        self.bouton("nav_impression", (24, 252, BARRE - 48, 32), "Rapport imprimable", "impression",
                    fond=ANTHRACITE, encre=BLANC, survol=BARRE_2, taille=10.5, alignement="center", bord=GRIS_CLAIR)
        self.rectangle("separateur", (24, 296, BARRE - 48, 1), GRIS)
        self.texte("filtres", (24, 302, 220, 20), "FILTRES", 9.5, GRIS_CLAIR, gras=True, decor=True)
        y = 324
        for groupe in SEGMENTS:
            h = HAUTEUR_SEGMENT.get(groupe, 62)
            if groupe == "projet" and self.id == "projet":
                self.segment(groupe, (14, y, BARRE - 28, h), synchro="projet_fiche",
                             libelle="Projet affiché (cette page)", defaut=PROJET_PAR_DEFAUT["valeur"])
            else:
                self.segment(groupe, (14, y, BARRE - 28, h))
            y += h + 4
        self.calcule("pied", (24, 868, 220, 24), mes("Pied de page"), 9, GRIS_CLAIR)

    def entete(self, titre=None, mention: str | None = None) -> None:
        self.rectangle("entete_filet", (X0, 28, 6, 36), JAUNE)
        if titre is None:
            self.texte("entete_titre", (X0 + 20, 20, 760, 50), self.titre, 23, ANTHRACITE, gras=True)
        else:
            self.calcule("entete_titre", (X0 + 20, 24, 900, 44), titre, 21, ANTHRACITE, gras=True)
        self.calcule("entete_sous_titre", (X0 + 20, 70, LC - 440, 26), mes("Périmètre"), 10.5, GRIS_TEXTE)
        if mention:
            self.texte("bandeau", (X0 + LC - 420, 34, 420, 26), mention, 10.5, ANTHRACITE, gras=True, alignement="right")
        else:
            self.calcule("bandeau", (X0 + LC - 420, 34, 420, 26), mes("Mention données"), 10.5, ANTHRACITE, gras=True,
                         alignement="right")

    def cartes(self, liste: list[tuple[str, str, str]], y: float = 108, h: float = 108,
               x0: float = X0, largeur: float = LC) -> None:
        for i, ((indicateur, titre, note), (x, w)) in enumerate(zip(liste, colonnes(len(liste), largeur, x0), strict=True), 1):
            self.kpi(i, (x, y, w, h), indicateur, titre, note)

    def kpi(self, i: int, boite: tuple, indicateur: str, titre: str, note: str) -> None:
        conteneur = {
            "title": [props(show=True, text=titre, fontSize=11.5, titleWrap=True, fontColor=GRIS_TEXTE)],
            "subTitle": [props(show=True, text=mes(note), fontSize=10.0, fontColor=GRIS_TEXTE, titleWrap=True)],
            "padding": [props(top=8.0, bottom=0.0, left=16.0, right=8.0)],
            "visualHeader": [props(show=False)],
            **alternatif(f"Indicateur : {titre}"),
        }
        self.poser(f"kpi{i}", "cardVisual", boite, req=requete({"Data": [mes(indicateur)]}),
                   conteneur=conteneur, objets={
            "layout": [props(maxTiles=1), props(DEFAUT, backgroundShow=False, paddingUniform=0, cellPadding=0)],
            "value": [props(DEFAUT, fontSize=26.0, fontColor=ANTHRACITE, fontFamily=SEMIBOLD, showBlankAs="—",
                            labelDisplayUnits=1.0, horizontalAlignment="left")],
            "label": [props(DEFAUT, show=False)], "outline": [props(DEFAUT, show=False)],
            "fillCustom": [props(DEFAUT, show=False)],
            "padding": [props(DEFAUT, paddingUniform=0, paddingIndividual=False)],
        })

    def graphique(self, nom: str, vtype: str, boite: tuple, roles: dict, titre: str, sous_titre: str | dict,
                  objets: dict, tri: tuple | None = None, alt=None, demo: bool = True) -> None:
        """`sous_titre` : texte, suivi de la mention des données ([DÉMO]) quand `demo`."""
        if isinstance(sous_titre, str) and demo:
            cle = f"{self.id} {nom}"
            SOUS_TITRES[cle] = sous_titre
            sous = mes(f"ST {cle}")
        else:
            sous = sous_titre
        if vtype in RESPONSIVES:
            objets = {**objets, "general": [props(responsive=False)]}
        self.poser(nom, vtype, boite, req=requete(roles, tri), objets=objets, conteneur={
            "title": [props(show=True, text=titre, fontSize=TITRE_VISUEL, titleWrap=True, fontColor=ANTHRACITE)],
            "subTitle": [props(show=True, text=sous, fontSize=10.0, fontColor=GRIS_TEXTE, titleWrap=True)],
            "spacing": [props(customizeSpacing=True, spaceBelowTitle=2.0, spaceBelowSubTitle=4.0,
                              spaceBelowTitleArea=6.0)],
            "padding": [props(top=10.0, bottom=8.0, left=14.0, right=14.0)],
            **alternatif(alt or f"{titre}. {sous_titre if isinstance(sous_titre, str) else ''}"),
        })

    def matrice(self, nom: str, boite: tuple, lignes: list, valeurs: list, titre: str, sous_titre, tri: tuple,
                *, colonnes_: list | None = None, rangs: float = 4.0, fonds: dict | None = None,
                encres: dict | None = None, demo: bool = True, police: float = 10.5) -> None:
        cellules = [props(fontSize=police, fontColorPrimary=ANTHRACITE, fontColorSecondary=ANTHRACITE,
                          backColorPrimary=BLANC, backColorSecondary=BLANC, wordWrap=True)]
        for mesure, regle in (fonds or {}).items():
            cellules.append(props({**CHAQUE_POINT, "metadata": ref(mes(mesure))}, backColor=mes(regle)))
        for mesure, regle in (encres or {}).items():
            cellules.append(props({**CHAQUE_POINT, "metadata": ref(mes(mesure))}, fontColor=mes(regle)))
        roles = {"Rows": lignes, "Values": [(mes(m), libelle) for m, libelle in valeurs]}
        if colonnes_:
            roles["Columns"] = colonnes_
        self.graphique(nom, "pivotTable", boite, roles, titre, sous_titre, {
            "stylePreset": [props(name="None")],
            "grid": [props(rowPadding=rangs, gridHorizontal=True, gridHorizontalColor=FOND, gridVertical=False,
                           textSize=police, outlineColor=GRIS_CLAIR)],
            "columnHeaders": [props(fontFamily=SEMIBOLD, fontSize=10.0, fontColor=GRIS_TEXTE, backColor=BLANC,
                                    wordWrap=True, autoSizeColumnWidth=True, alignment="Center")],
            "rowHeaders": [props(fontSize=police, fontColor=ANTHRACITE, showExpandCollapseButtons=False, wordWrap=True)],
            "values": cellules,
            "subTotals": [props(rowSubtotals=False, columnSubtotals=False)],
            "columnTotal": [props(show=False)] if colonnes_ else [props()],
        }, tri, demo=demo)

    def actions(self, boite: tuple, taille: float = 12.0) -> None:
        """« Que faire ensuite » : trois actions calculées par des règles explicites (KPI.md)."""
        x, y, w, h = boite
        self.rectangle("actions_fond", boite, ANTHRACITE)
        self.texte("actions_titre", (x + 20, y + 12, w - 40, 30), "Que faire ensuite", 14, JAUNE, gras=True)
        self.calcule("actions_note", (x + 20, y + 42, w - 40, 22), mes("Badge démo"), 9.5, GRIS_CLAIR)
        pas = (h - 76) / 3
        for n in (1, 2, 3):
            hy = y + 70 + (n - 1) * pas
            self.calcule(f"action{n}_num", (x + 20, hy, 34, 34), mes(f"Numéro action {n}"), 20, JAUNE, gras=True)
            self.calcule(f"action{n}", (x + 60, hy + 2, w - 80, pas - 6), mes(f"Action {n}"), taille, BLANC)


# ---------------------------------------------------------------- champs
PROJET, CLIENT = col("Projets", "Projet"), col("Projets", "Client")
MOIS, DATE, SEMAINE = col("Calendrier", "Mois"), col("Calendrier", "Date"), col("Calendrier", "Semaine")
ETAT, TYPE = col("Livrables", "État"), col("Types de livrable", "Type de livrable")
TYPE_COURT = col("Types de livrable", "Type")
RESULTAT, MODELE = col("Générations", "Résultat"), col("Générations", "Modèle")
SECTION, ROLE = col("Sections", "Section"), col("Sections", "À quoi sert la section")
AXE, GRAVITE = col("Constats", "Axe"), col("Constats", "Gravité")
AXE_INI, VAGUE = col("Initiatives", "Axe de l'initiative"), col("Initiatives", "Vague")
RAPPORT = col("Rapports", "Rapport")
ESSAI, PAS = col("Entraînements", "Essai"), col("Courbe de validation", "Pas")
TACHE, MODELE_TESTE = col("Scores", "Tâche"), col("Scores", "Modèle testé")
TYPE_ERREUR, EXPLICATION = col("Types d'erreur", "Type d'erreur"), col("Types d'erreur", "Explication")


def barres_projet(p: Page, boite: tuple) -> None:
    constats, recos, livrables = mes("Constats"), mes("Recommandations retenues"), mes("Livrables")
    p.graphique("par_projet", "clusteredBarChart", boite,
                {"Category": [PROJET], "Y": [(livrables, "Livrables"), (constats, "Constats"),
                                             (recos, "Recommandations retenues")],
                 "Tooltips": [(mes("Taux d'erreur de l'IA"), "Taux d'erreur de l'IA"), (mes("Client du projet"), "Client")]},
                "Activité par projet", "Clic droit sur un projet pour filtrer", {
                    "categoryAxis": axe(maxMarginFactor=48, fontSize=9.5, gridlineShow=False),
                    "valueAxis": sans_axe(start=0.0),
                    "legend": legende(),
                    "labels": etiquettes(labelPosition="OutsideEnd"),
                    "dataPoint": [props(serie(livrables), fill=ANTHRACITE), props(serie(constats), fill=GRIS),
                                  props(serie(recos), fill=JAUNE)]},
                tri=(livrables, "Descending"))


def appels_par_mois(p: Page, boite: tuple, titre: str = "Appels au modèle par mois") -> None:
    appels = mes("Appels au modèle")
    p.graphique("par_mois", "columnChart", boite,
                {"Category": [MOIS], "Series": [RESULTAT], "Y": [(appels, "Appels")],
                 "Tooltips": [(mes("Taux d'erreur de l'IA"), "Taux d'erreur de l'IA"),
                              (mes("Temps moyen par appel"), "Temps moyen par appel")]},
                titre, "Rouge : erreurs ; gris clair : refus voulus", {
                    "categoryAxis": axe(gridlineShow=False, fontSize=10.0),
                    "valueAxis": axe(start=0.0, fontSize=9.5, gridlineShow=True, gridlineColor=FOND),
                    "legend": legende(),
                    "labels": [props(show=False)],
                    "dataPoint": couleurs(RESULTAT, COULEURS_RESULTAT)},
                tri=(MOIS, "Ascending"))


def livrables_par_etat(p: Page, boite: tuple) -> None:
    p.graphique("etats", "donutChart", boite,
                {"Category": [ETAT], "Y": [(mes("Livrables"), "Livrables")],
                 "Tooltips": [(mes("Phrases non vérifiées"), "Phrases non vérifiées")]},
                "Livrables par état", "Créés dans la période", {
                    "legend": legende("Right"),
                    "labels": [props(show=True, fontSize=10.5, color=ANTHRACITE, labelStyle="Data")],
                    "slices": [props(innerRadiusRatio=58)],
                    "dataPoint": couleurs(ETAT, COULEURS_ETAT)},
                tri=(col("Livrables", "État"), "Ascending"))


def recos_par_rapport(p: Page, boite: tuple) -> None:
    valid, avalider, manq = mes("Recommandations validées"), mes("Recommandations à valider"), mes("Recommandations manquantes")
    p.graphique("recos_rapport", "barChart", boite,
                {"Category": [RAPPORT], "Y": [(valid, "Validées"), (avalider, "À valider"), (manq, "Manquantes")],
                 "Tooltips": [(mes("Alerte contrôle"), "Contrôle"), (mes("Alerte manquants"), "Numéros manquants"),
                              (mes("Recommandations annoncées"), "Annoncées par le rapport")]},
                "Recommandations par rapport d'audit", "En rouge : numéros annoncés mais absents", {
                    "categoryAxis": axe(maxMarginFactor=50, fontSize=9.5, gridlineShow=False),
                    "valueAxis": sans_axe(start=0.0),
                    "legend": legende(),
                    "labels": etiquettes(labelPosition="InsideCenter", color=BLANC),
                    "dataPoint": [props(serie(valid), fill=ANTHRACITE), props(serie(avalider), fill=GRIS),
                                  props(serie(manq), fill=ROUGE)]},
                tri=(RAPPORT, "Ascending"))


# ---------------------------------------------------------------- pages
def synthese() -> Page:
    p = Page("synthese")
    p.entete()
    p.cartes([("Projets", "Projets", "Note projets"), ("Livrables", "Livrables", "Note livrables"),
              ("Taux d'erreur de l'IA", "Taux d'erreur (hors refus)", "Note erreur"),
              ("Temps moyen affiché", "Temps moyen par appel", "Note temps"),
              ("Entraînements", "Entraînements réalisés", "Note entraînements")])
    y1, h1 = 232, 318
    appels_par_mois(p, (X0, y1, 820, h1))
    livrables_par_etat(p, (X0 + 820 + G, y1, LC - 820 - G, h1))
    y2 = y1 + h1 + G
    barres_projet(p, (X0, y2, 640, BAS - y2))
    p.actions((X0 + 640 + G, y2, LC - 640 - G, BAS - y2))
    return p


def projet() -> Page:
    p = Page("projet")
    p.entete(mes("Titre du projet"))
    y0, h0 = 108, 150
    p.rectangle("fiche_fond", (X0, y0, FICHE, h0), BLANC, bord=GRIS_CLAIR)
    p.graphique("logo", "pivotTable", (X0 + 8, y0 + 8, 134, h0 - 16), {"Rows": [col("Projets", "Logo")]},
                "", "", {"stylePreset": [props(name="None")],
                         "grid": [props(gridHorizontal=False, gridVertical=False, outlineColor=BLANC, imageHeight=96.0)],
                         "columnHeaders": [props(fontSize=1.0, fontColor=BLANC, backColor=BLANC)],
                         "rowHeaders": [props(showExpandCollapseButtons=False)]},
                alt="Logo du client", demo=False)
    tx = X0 + 156
    p.calcule("fiche_client", (tx, y0 + 12, FICHE - 170, 26), mes("Client du projet"), 13, ANTHRACITE, gras=True)
    p.calcule("fiche_dates", (tx, y0 + 40, FICHE - 170, 22), mes("Dates du projet"), 10.5, GRIS_TEXTE)
    p.calcule("fiche_demande", (tx, y0 + 66, FICHE - 170, h0 - 74), mes("Demande du projet"), 10.5, ANTHRACITE)
    p.cartes([("Documents", "Documents", "Note documents"),
              ("Recommandations retenues", "Recommandations", "Recommandations sur annoncées"),
              ("Rapports en alerte", "Rapports en alerte", "Note rapports"),
              ("Constats", "Constats", "Note constats")], y=y0, h=h0, x0=X0 + FICHE + G, largeur=LC - FICHE - G)
    y1, h1 = y0 + h0 + G, 292
    recos_par_rapport(p, (X0, y1, 620, h1))
    p.graphique("constats_axe", "barChart", (X0 + 620 + G, y1, LC - 620 - G, h1),
                {"Category": [AXE], "Series": [GRAVITE], "Y": [(mes("Constats"), "Constats")]},
                "Constats par axe et gravité", "Axe : celui de l'initiative qui traite le constat", {
                    "categoryAxis": axe(maxMarginFactor=60, fontSize=9.0, gridlineShow=False),
                    "valueAxis": sans_axe(start=0.0),
                    "legend": legende(),
                    "labels": etiquettes(labelPosition="InsideCenter", color=BLANC),
                    "dataPoint": couleurs(GRAVITE, COULEURS_GRAVITE)},
                tri=(mes("Constats"), "Descending"))
    y2 = y1 + h1 + G
    w1, w2 = 500, 300
    ini = mes("Initiatives")
    p.graphique("feuille", "barChart", (X0, y2, w1, BAS - y2),
                {"Category": [AXE_INI], "Series": [VAGUE], "Y": [(ini, "Initiatives")],
                 "Tooltips": [(mes("Constats traités"), "Constats traités")]},
                "Feuille de route : initiatives par axe et vague", "Vague 1 d'abord", {
                    "categoryAxis": axe(maxMarginFactor=70, fontSize=9.0, gridlineShow=False),
                    "valueAxis": sans_axe(start=0.0),
                    "legend": legende(),
                    "labels": etiquettes(labelPosition="InsideCenter"),
                    "dataPoint": couleurs(VAGUE, COULEURS_VAGUE)},
                tri=(ini, "Descending"))
    statut = col("Livrables", "État")
    p.graphique("avancement", "hundredPercentStackedBarChart", (X0 + w1 + G, y2, w2, BAS - y2),
                {"Category": [TYPE_COURT], "Series": [statut], "Y": [(mes("Livrables"), "Livrables")],
                 "Tooltips": [TYPE]},
                "Avancement des livrables", "Part de chaque état, par type", {
                    "categoryAxis": axe(maxMarginFactor=40, fontSize=9.5, gridlineShow=False),
                    "valueAxis": sans_axe(),
                    "legend": legende(),
                    "labels": [props(show=False)],
                    "dataPoint": couleurs(statut, COULEURS_ETAT)},
                tri=(TYPE_COURT, "Ascending"))
    nv = mes("Taux de phrases vérifiées")
    p.graphique("sections", "clusteredBarChart", (X0 + w1 + w2 + 2 * G, y2, LC - w1 - w2 - 2 * G, BAS - y2),
                {"Category": [SECTION], "Y": [(nv, "Phrases vérifiées")],
                 "Tooltips": [ROLE, col("Sections", "Livrable de la section"), (mes("Phrases générées"), "Phrases générées"),
                              (mes("Sections refusées"), "Sections refusées")]},
                "Qualité par section", "Phrases vérifiées ; survol : à quoi sert la section", {
                    "categoryAxis": axe(maxMarginFactor=55, fontSize=9.0, gridlineShow=False),
                    "valueAxis": sans_axe(start=0.0, end=1.18),
                    "labels": etiquettes(labelPosition="OutsideEnd", labelDisplayUnits=0.0),
                    "dataPoint": [props(serie(nv), fill=ANTHRACITE)]},
                tri=(nv, "Ascending"))
    return p


def qualite() -> Page:
    p = Page("qualite")
    p.entete()
    p.cartes([("Taux de phrases vérifiées", "Phrases vérifiées", "Note vérifiées"),
              ("Citations sans source affiché", "Citations sans source", "Note citations"),
              ("Taux de refus", "Refus faute de preuve", "Note refus"),
              ("Sorties invalides", "Sorties invalides", "Note invalides")])
    y1, h1 = 232, 310
    nv, rf, er = mes("Taux de phrases non vérifiées"), mes("Taux de refus"), mes("Taux d'erreur de l'IA")
    p.graphique("tendance", "lineChart", (X0, y1, 820, h1),
                {"Category": [SEMAINE], "Y": [(er, "Taux d'erreur"), (nv, "Phrases non vérifiées"),
                                              (rf, "Refus voulus (neutre)")],
                 "Tooltips": [(mes("Appels au modèle"), "Appels au modèle")]},
                "Erreurs de l'IA par semaine", "Au jour : filtre Période ; le refus n'est pas une erreur", {
                    "categoryAxis": axe("Semaine du", axisType="Categorical", fontSize=9.0, gridlineShow=False),
                    "valueAxis": axe(start=0.0, fontSize=9.5, gridlineShow=True, gridlineColor=FOND),
                    "legend": legende(),
                    "labels": [props(show=False)],
                    "lineStyles": [props(strokeWidth=2.0, showMarker=True, markerSize=3.0),
                                   props(serie(nv), lineStyle="dashed"), props(serie(rf), lineStyle="dotted")],
                    "dataPoint": [props(serie(er), fill=ROUGE), props(serie(nv), fill=ANTHRACITE),
                                  props(serie(rf), fill=GRIS_CLAIR)]},
                tri=(SEMAINE, "Ascending"))
    erreurs = mes("Erreurs")
    p.graphique("types", "clusteredBarChart", (X0 + 820 + G, y1, LC - 820 - G, h1),
                {"Category": [TYPE_ERREUR], "Y": [(erreurs, "Erreurs")], "Tooltips": [EXPLICATION]},
                "Erreurs par type", "Survol : ce que signifie chaque type", {
                    "categoryAxis": axe(maxMarginFactor=45, fontSize=10.0, gridlineShow=False),
                    "valueAxis": sans_axe(start=0.0),
                    "labels": etiquettes(labelPosition="InsideEnd", color=BLANC),
                    "dataPoint": [props(serie(erreurs), fill=ANTHRACITE)]},
                tri=(erreurs, "Descending"))
    y2 = y1 + h1 + G
    p.matrice("alertes", (X0, y2, 820, BAS - y2), [RAPPORT],
              [("Alerte projet", "Projet"), ("Alerte annoncées", "Annoncées"), ("Alerte retenues", "Retenues"),
               ("Alerte manquants", "Manquants"), ("Alerte contrôle", "Contrôle")],
              "Alertes : recommandations extraites ≠ annoncées", "Rapports à vérifier par le consultant, les plus graves d'abord",
              (mes("Alerte manquants"), "Descending"), rangs=5.0, encres={"Alerte contrôle": "Couleur de l'alerte"},
              police=10.0)
    ok, rf2 = mes("Taux de phrases vérifiées"), mes("Taux de refus")
    p.graphique("modeles", "clusteredColumnChart", (X0 + 820 + G, y2, LC - 820 - G, BAS - y2),
                {"Category": [MODELE], "Y": [(ok, "Phrases vérifiées"), (rf2, "Refus")],
                 "Tooltips": [(mes("Appels au modèle"), "Appels"), (mes("Temps moyen par appel"), "Temps moyen")]},
                "Qualité par modèle", "Modèle utilisé par l'application", {
                    "categoryAxis": axe(fontSize=9.5, gridlineShow=False),
                    "valueAxis": sans_axe(start=0.0, end=1.0),
                    "legend": legende(),
                    "labels": etiquettes(labelPosition="OutsideEnd"),
                    "dataPoint": [props(serie(ok), fill=ANTHRACITE), props(serie(rf2), fill=GRIS)]},
                tri=(MODELE, "Ascending"))
    return p


def entrainement() -> Page:
    p = Page("entrainement")
    p.entete(mention="Valeurs réelles des entraînements")
    p.cartes([("Entraînements", "Entraînements", "Note essais"), ("Modèle adopté", "Modèle adopté", "Note modèle adopté"),
              ("Meilleure erreur affichée", "Erreur de validation retenue", "Note erreur adoptée"),
              ("Exemples d'entraînement", "Exemples d'entraînement", "Note exemples")])
    y1, h1 = 232, 236
    p.matrice("essais", (X0, y1, LC, h1), [ESSAI],
              [("Essai date", "Date"), ("Essai plateforme", "Plateforme"), ("Essai exemples", "Exemples"),
               ("Essai durée", "Durée"), ("Essai meilleure erreur", "Meilleure erreur de validation"),
               ("Essai arrêt", "Arrêt"), ("Essai décision", "Décision"), ("Essai résultat", "Ce qu'il faut retenir")],
              "Les entraînements, dans l'ordre", "Valeurs réelles (docs/19 et docs/20)",
              (col("Entraînements", "Essai"), "Ascending"), rangs=6.0, demo=False)
    y2 = y1 + h1 + G
    perte, meilleur = mes("Erreur de validation"), mes("Erreur au meilleur pas")
    p.graphique("courbe", "lineChart", (X0, y2, 620, BAS - y2),
                {"Category": [PAS], "Series": [ESSAI], "Y": [(perte, "Erreur de validation")]},
                "Courbe de validation", "Valeurs réelles · mesurée tous les 20 pas ; essai 1 : pas de courbe consignée", {
                    "categoryAxis": axe("Pas d'entraînement", axisType="Scalar", fontSize=9.5, gridlineShow=False),
                    "valueAxis": axe(fontSize=9.5, gridlineShow=True, gridlineColor=FOND, start=0.14, end=0.30),
                    "legend": legende(),
                    "labels": [props(show=False)],
                    "lineStyles": [props(strokeWidth=3.0, showMarker=True, markerSize=6.0)],
                    "dataPoint": couleurs(ESSAI, COULEURS_ESSAI)},
                tri=(PAS, "Ascending"), demo=False)
    taux = mes("Taux de réussite")
    p.graphique("taches", "clusteredBarChart", (X0 + 620 + G, y2, LC - 620 - G, BAS - y2),
                {"Category": [TACHE], "Series": [MODELE_TESTE], "Y": [(taux, "Réussite")],
                 "Tooltips": [(mes("Exemples réussis"), "Réussis"), (mes("Exemples testés"), "Testés")]},
                "Réussite par tâche : modèle de base contre modèles entraînés",
                "Valeurs réelles · exemples de test jamais vus à l'entraînement", {
                    "categoryAxis": axe(maxMarginFactor=40, fontSize=9.5, gridlineShow=False),
                    "valueAxis": sans_axe(start=0.0, end=1.14),
                    "legend": legende(),
                    "labels": etiquettes(labelPosition="OutsideEnd", fontSize=8.5),
                    "dataPoint": couleurs(MODELE_TESTE, COULEURS_MODELE)},
                tri=(TACHE, "Ascending"), demo=False)
    return p


def impression() -> Page:
    p = Page("impression", largeur=A4_L, hauteur=A4_H, barre=False)
    for i, groupe in enumerate(SEGMENTS):
        p.segment(groupe, (40 + i * 110, 0, 100, 40), masque=True)
    x, w = 52, A4_L - 104
    p.rectangle("titre_filet", (x, 48, 8, 40), JAUNE)
    p.texte("titre", (x + 22, 42, 520, 52), "Cadrage · rapport de direction", 21, ANTHRACITE, gras=True)
    p.bouton("retour", (A4_L - 52 - 120, 52, 120, 32), "←  Synthèse", "synthese", fond=FOND, encre=GRIS_TEXTE,
             survol=GRIS_CLAIR, taille=10.0, alignement="center")
    p.calcule("perimetre", (x, 100, w, 22), mes("Périmètre"), 10, GRIS_TEXTE)
    p.calcule("mention", (x, 124, w, 22), mes("Mention données"), 10, ANTHRACITE, gras=True)
    p.cartes([("Projets", "Projets", "Note projets"), ("Livrables", "Livrables", "Note livrables"),
              ("Taux d'erreur de l'IA", "Taux d'erreur", "Note erreur"),
              ("Rapports en alerte", "Rapports en alerte", "Note rapports")], y=156, h=100, x0=x, largeur=w)
    p.actions((x, 272, w, 200), taille=11.0)
    appels_par_mois(p, (x, 488, w, 200), "Activité de l'IA par mois")
    (x1, w1), (x2, w2) = colonnes(2, w, x)
    livrables_par_etat(p, (x1, 704, w1, 262))
    barres_projet(p, (x2, 704, w2, 262))
    recos_par_rapport(p, (x, 982, w, 244))
    p.texte("limites", (x, 1232, w, 24), "Limites : une source qui existe ne prouve pas qu'elle soutient la phrase ; "
            "les projets [DÉMO] sont inventés.", 9, GRIS_TEXTE)
    return p


# ---------------------------------------------------------------- écriture
def ecrire_json(chemin: Path, objet) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(objet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def pages() -> list[Page]:
    """Construit les pages (et remplit SOUS_TITRES, lu ensuite par le modèle)."""
    return [synthese(), projet(), qualite(), entrainement(), impression()]


def construire_rapport(racine: Path, theme: Path, liste: list[Page]) -> None:
    ecrire_json(racine / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../CadrageIA.SemanticModel"}},
    })
    d = racine / "definition"
    import_version = {"visual": "2.7.0", "report": "3.2.0", "page": "2.1.0"}
    ecrire_json(d / "version.json", {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    ecrire_json(d / "report.json", {
        "$schema": f"{SCHEMA}/report/3.2.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": THEME_BASE, "reportVersionAtImport": import_version, "type": "SharedResources"},
            "customTheme": {"name": theme.name, "reportVersionAtImport": import_version,
                            "type": "RegisteredResources"},
        },
        "objects": {"outspacePane": [props(expanded=False, visible=False)]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": THEME_BASE, "path": f"BaseThemes/{THEME_BASE}.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": theme.name, "path": theme.name, "type": "CustomTheme"}]},
        ],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True},
    })
    ressources = racine / "StaticResources" / "RegisteredResources"
    ressources.mkdir(parents=True, exist_ok=True)
    shutil.copy(theme, ressources / theme.name)

    ecrire_json(d / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
        "pageOrder": list(PAGES), "activePageName": VISIBLES[0]})
    for p in liste:
        masquee = p.id in MASQUEES
        page = {
            "$schema": f"{SCHEMA}/page/2.1.0/schema.json", "name": p.id, "displayName": p.titre,
            "displayOption": "FitToPage", "height": p.hauteur, "width": p.largeur,
            "objects": {"background": [props(color=BLANC if masquee else FOND, transparency=0.0)],
                        "outspace": [props(color=FOND, transparency=0.0)]}}
        if masquee:
            page["visibility"] = "HiddenInViewMode"
        ecrire_json(d / "pages" / p.id / "page.json", page)
        for v in p.visuels:
            ecrire_json(d / "pages" / p.id / "visuals" / v["name"] / "visual.json", v)
