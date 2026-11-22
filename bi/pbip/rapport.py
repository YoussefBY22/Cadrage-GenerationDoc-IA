"""Rapport PBIR par acteur : quatre pages visibles et une page imprimable masquée.

Règles de conception, avec leurs sources, dans docs/14 §6 :
- titres nominaux ; sous-titre périmètre, mesure, période ; le message vit dans une zone « Constat » ;
- titres de visuels neutres, tous à la même taille ;
- au plus 4 KPI par page, en mesures numériques (épinglables avec alerte dans le Service) ;
- peu de texte : décisions, formules et seuils sont dans bi/KPI.md, pas sur les pages ;
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
    CONSULTANT,
    GRIS,
    GRIS_CLAIR,
    GRIS_TEXTE,
    JAUNE,
    RESPONSABLE,
    ROUGE,
    SUFFIXE,
    TOUS,
    TOUT,
)
from pbir import CHAQUE_POINT, DEFAUT, SCHEMA, SCHEMA_VISUEL, SEMIBOLD, col, mes, props, ref, requete, serie

L, H, BARRE = 1600, 900, 256
A4_L, A4_H = 900, 1273
X0, LC, G = 288, 1280, 16
BAS = H - 24
HAUT_CORPS = 330
HAUT_RECOS = 180
HAUT_SUITE = HAUT_CORPS + HAUT_RECOS + G
BLANC, FOND, BARRE_2 = "#FFFFFF", "#F6F6FA", "#3C3C48"
THEME_BASE = "CY26SU02"
TITRE_VISUEL = 13.0
MAX_ALT = 250  # limite de Power BI pour un texte alternatif

PAGES = {"synthese": "Synthèse", "production": "Production", "validation": "Validation",
         "administration": "Administration", "impression": "Rapport"}
VISIBLES = ("synthese", "production", "validation", "administration")
MASQUEES = ("impression",)
SEGMENTS = {  # groupe de synchronisation → (libellé, table, colonne, valeur par défaut)
    "periode": ("Période (flux)", "Choix de période", "Période choisie", TOUT),
    "client": ("Client", "Choix du client", "Client choisi", TOUS),
    "type": ("Type de livrable", "Choix du type", "Type choisi", TOUS),
    "consultant": ("Consultant", "Choix du consultant", "Consultant choisi", TOUS),
}
RESPONSIVES = ("barChart", "clusteredBarChart", "clusteredColumnChart", "lineChart")


def colonnes(n: int, largeur: float = LC, x0: float = X0) -> list[tuple[float, float]]:
    """n colonnes égales séparées par la gouttière : [(x, largeur), …]."""
    w = (largeur - G * (n - 1)) / n
    return [(x0 + i * (w + G), w) for i in range(n)]


def alternatif(texte) -> dict:
    """Texte alternatif, statique ou calculé par une mesure."""
    return {"general": [props(altText=texte[:MAX_ALT] if isinstance(texte, str) else texte)]}


def selection(table: str, colonne: str, valeur: str) -> dict:
    """Sélection enregistrée d'un segment (« Tous » par défaut)."""
    litteral = "'" + valeur.replace("'", "''") + "'"
    return {"properties": {"filter": {"filter": {
        "Version": 2, "From": [{"Name": "c", "Entity": table, "Type": 0}],
        "Where": [{"Condition": {"In": {
            "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": colonne}}],
            "Values": [[{"Literal": {"Value": litteral}}]]}}}]}}}}


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
              decor: bool = False) -> None:
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
        # Un tabOrder négatif sort l'objet de l'ordre de tabulation
        ordre = -(rang + 1) if decor or masque else rang * 100
        objet = {"$schema": SCHEMA_VISUEL, "name": f"{self.id}_{nom}",
                 "position": {"x": round(x, 2), "y": round(y, 2), "z": rang * 100, "width": round(w, 2),
                              "height": round(h, 2), "tabOrder": ordre},
                 "visual": visuel}
        if masque:
            objet["isHidden"] = True
        self.visuels.append(objet)

    @staticmethod
    def nu(**autres) -> dict:
        """Conteneur sans fond, titre, bordure ni en-tête : pour les formes et les textes."""
        base = {"background": [props(show=False)], "title": [props(show=False)], "border": [props(show=False)],
                "visualHeader": [props(show=False)],
                "padding": [props(top=0.0, bottom=0.0, left=0.0, right=0.0)]}
        return {**base, **autres}

    def rectangle(self, nom: str, boite: tuple, fond: str) -> None:
        self.poser(nom, "shape", boite, decor=True, conteneur=self.nu(), objets={
            "shape": [props(tileShape="rectangle")],
            "fill": [props(show=True), props(DEFAUT, fillColor=fond, transparency=0.0)],
            "outline": [props(show=False)]})

    def texte(self, nom: str, boite: tuple, texte: str, taille: float, encre: str, gras: bool = False,
              alignement: str = "left", vertical: str = "middle", decor: bool = False) -> None:
        # Une forme, et non une zone de texte : celle-ci affiche des barres de défilement dès qu'elle est juste.
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
            autres["spacing"] = [props(customizeSpacing=True, spaceBelowTitle=5.0)]
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

    def segment(self, groupe: str, boite: tuple, masque: bool = False) -> None:
        libelle, table, colonne, defaut = SEGMENTS[groupe]
        champ = col(table, colonne)
        self.poser(
            f"segment_{groupe}", "slicer", boite, req=requete({"Values": [champ]}), synchro=groupe, masque=masque,
            objets={
                "data": [props(mode="Dropdown")],
                "general": [selection(table, colonne, defaut)],
                "selection": [props(selectAllCheckboxEnabled=False, singleSelect=True, strictSingleSelect=True)],
                "header": [props(show=True, text=libelle, fontColor=BLANC, textSize=11.0)],
                "items": [props(fontColor=BLANC, background=BARRE_2, textSize=11.0)],
            },
            conteneur={"background": [props(show=False)], "title": [props(show=False)],
                       "visualHeader": [props(show=False)], "border": [props(show=False)],
                       "padding": [props(top=2.0, bottom=2.0, left=4.0, right=4.0)],
                       **alternatif(f"Filtre {libelle}, synchronisé sur toutes les pages")})

    # ------------------------------------------------------------ éléments communs
    def barre_laterale(self) -> None:
        self.rectangle("barre", (0, 0, BARRE, H), ANTHRACITE)
        self.rectangle("logo_carre", (24, 28, 30, 30), JAUNE)
        self.texte("logo_mot", (66, 18, 180, 50), "Cadrage", 22, BLANC, gras=True, decor=True)
        self.texte("logo_legende", (24, 70, 220, 24), "Pilotage de l'assistant IA", 10.5, GRIS_CLAIR, decor=True)
        for i, pid in enumerate(VISIBLES):
            active = pid == self.id
            self.bouton(f"nav_{pid}", (0, 108 + i * 42, BARRE, 40), PAGES[pid], pid,
                        fond=JAUNE if active else ANTHRACITE, encre=ANTHRACITE if active else BLANC,
                        survol=JAUNE if active else BARRE_2, gras=active)
        self.bouton("nav_impression", (24, 288, BARRE - 48, 38), "Rapport imprimable", "impression",
                    fond=ANTHRACITE, encre=BLANC, survol=BARRE_2, taille=11.0, alignement="center", bord=GRIS_CLAIR)
        self.rectangle("separateur", (24, 346, BARRE - 48, 1), GRIS)
        self.texte("filtres", (24, 358, 220, 22), "FILTRES", 9.5, GRIS_CLAIR, gras=True, decor=True)
        for i, groupe in enumerate(SEGMENTS):
            self.segment(groupe, (16, 386 + i * 92, BARRE - 32, 76))
        self.calcule("pied", (24, 848, 220, 40), mes("Pied de page"), 9.5, GRIS_CLAIR)

    def entete(self) -> None:
        self.rectangle("entete_filet", (X0, 30, 6, 38), JAUNE)
        self.texte("entete_titre", (X0 + 20, 22, 700, 54), self.titre, 24, ANTHRACITE, gras=True)
        self.calcule("entete_sous_titre", (X0 + 20, 78, LC - 20, 30), mes(f"Sous-titre {self.id}"), 10.5, GRIS_TEXTE)
        self.calcule("bandeau", (X0 + LC - 360, 38, 360, 28), mes("Bandeau données"), 10, GRIS_TEXTE, gras=True,
                     alignement="right")
        self.rectangle("constat_fond", (X0, 114, LC, 56), ANTHRACITE)
        self.texte("constat_etiquette", (X0 + 20, 114, 110, 56), "CONSTAT", 10.5, JAUNE, gras=True, decor=True)
        self.calcule("constat", (X0 + 130, 128, LC - 150, 38), mes(f"Constat {self.id}"), 12.5, BLANC, gras=True)

    def cartes(self, liste: list[tuple[str, str | None]]) -> None:
        assert len(liste) <= 4, "au plus 4 KPI par page"
        for i, ((nom, titre), (x, w)) in enumerate(zip(liste, colonnes(len(liste)), strict=True), 1):
            self.kpi(i, (x, 186, w, 128), nom, titre)

    def kpi(self, i: int, boite: tuple, indicateur: str, titre: str | None) -> None:
        x, y, w, h = boite
        titre = titre or indicateur
        conteneur = {
            "title": [props(show=True, text=titre, fontSize=TITRE_VISUEL, titleWrap=True)],
            "subTitle": [props(show=True, text=mes(f"Note {indicateur}"), fontSize=10.0, fontColor=GRIS_TEXTE,
                               titleWrap=True)],
            "padding": [props(top=8.0, bottom=0.0, left=16.0, right=8.0)],
            "visualHeader": [props(show=False)],
            **alternatif(f"Indicateur : {titre}"),
        }
        self.poser(f"kpi{i}", "cardVisual", (x, y, w, h), req=requete({"Data": [mes(indicateur)]}),
                   conteneur=conteneur, objets={
            "layout": [props(maxTiles=1), props(DEFAUT, backgroundShow=False, paddingUniform=0, cellPadding=0)],
            "value": [props(DEFAUT, fontSize=28.0, fontColor=ANTHRACITE, fontFamily=SEMIBOLD, showBlankAs="Non mesuré",
                            labelDisplayUnits=1.0, horizontalAlignment="left")],
            "label": [props(DEFAUT, show=False)], "outline": [props(DEFAUT, show=False)],
            "fillCustom": [props(DEFAUT, show=False)],
            "padding": [props(DEFAUT, paddingUniform=0, paddingIndividual=False)],
        })

    def graphique(self, nom: str, vtype: str, boite: tuple, roles: dict, titre: str, sous_titre, objets: dict,
                  tri: tuple | None = None, alt=None) -> None:
        if vtype in RESPONSIVES:
            objets = {**objets, "general": [props(responsive=False)]}
        self.poser(nom, vtype, boite, req=requete(roles, tri), objets=objets, conteneur={
            "title": [props(show=True, text=titre, fontSize=TITRE_VISUEL, titleWrap=True)],
            "subTitle": [props(show=True, text=sous_titre, fontSize=10.5, fontColor=GRIS_TEXTE, titleWrap=True)],
            "spacing": [props(customizeSpacing=True, spaceBelowTitle=2.0, spaceBelowSubTitle=4.0,
                              spaceBelowTitleArea=6.0)],
            "padding": [props(top=10.0, bottom=8.0, left=16.0, right=16.0)],
            **alternatif(alt or f"{titre}. {sous_titre}"),
        })

    def tableau(self, nom: str, boite: tuple, ligne: tuple | dict, valeurs: list, titre: str, sous_titre: str,
                tri: tuple, *, rangs: float = 4.0, fonds: dict | None = None, encres: dict | None = None,
                alt=None) -> None:
        # Une matrice à une seule colonne de lignes : le visuel « table » reste vide avec ce PBIR.
        cellules = [props(fontSize=10.5, fontColorPrimary=ANTHRACITE, fontColorSecondary=ANTHRACITE,
                          backColorPrimary=BLANC, backColorSecondary=BLANC)]
        for mesure, regle in (fonds or {}).items():
            cellules.append(props({**CHAQUE_POINT, "metadata": ref(mes(mesure))}, backColor=mes(regle)))
        for mesure, regle in (encres or {}).items():
            cellules.append(props({**CHAQUE_POINT, "metadata": ref(mes(mesure))}, fontColor=mes(regle)))
        self.graphique(nom, "pivotTable", boite,
                       {"Rows": [ligne], "Values": [(mes(m), libelle) for m, libelle in valeurs]},
                       titre, sous_titre, {
            "stylePreset": [props(name="None")],
            "grid": [props(rowPadding=rangs, gridHorizontal=True, gridHorizontalColor=FOND, gridVertical=False,
                           textSize=10.5, outlineColor=GRIS_CLAIR)],
            "columnHeaders": [props(fontFamily=SEMIBOLD, fontSize=10.0, fontColor=GRIS_TEXTE, backColor=BLANC,
                                    wordWrap=True, autoSizeColumnWidth=True, columnAdjustment="growToFit",
                                    alignment="Center")],
            "rowHeaders": [props(fontSize=10.5, fontColor=ANTHRACITE, showExpandCollapseButtons=False)],
            "values": cellules,
            "subTotals": [props(rowSubtotals=False, columnSubtotals=False)],
        }, tri, alt)

    def recommandations(self, boite: tuple, acteur: str | None, titre: str) -> None:
        suffixe = SUFFIXE[acteur]
        valeurs = [(f"Reco rang{suffixe}", "Priorité"), (f"Reco nombre{suffixe}", "Livrables")]
        if acteur is None:
            valeurs.append(("Reco pour", "Pour"))
        valeurs.append((f"Reco action{suffixe}", "Action"))
        self.tableau("recos", boite, (col("Règles", "Libellé"), "Constat"), valeurs, titre,
                     mes(f"Reco état{suffixe}"), (mes(f"Reco rang{suffixe}"), "Ascending"), rangs=3.0, alt=titre)

    def prevision(self, boite: tuple) -> None:
        """Série régulière par quinzaine, prévision et bornes : des formes de point, pas seulement des couleurs."""
        x, y, w, h = boite
        note = 62
        reel, prevu = mes("Soumissions réelles"), mes("Prévision")
        bas, haut = mes("Borne basse"), mes("Borne haute")
        date = col("Série de prévision", "Fin de quinzaine")
        self.graphique(
            "prevision", "lineChart", (x, y, w, h - note),
            {"Category": [date],
             "Y": [(reel, "Réel"), (prevu, "Prévision"), (haut, "Borne haute"), (bas, "Borne basse")]},
            "Soumissions en relecture", "Par quinzaine", {
                # Dates régulières (pas de 14 j) ; en axe continu, Power BI traduirait les mois en anglais
                "categoryAxis": axe(axisType="Categorical", fontSize=9.0, gridlineShow=False,
                                    preferredCategoryWidth=20.0, maxMarginFactor=30),
                "valueAxis": axe(start=0.0, fontSize=9.5, gridlineShow=True, gridlineColor=FOND),
                "legend": [props(show=True, position="TopRight", showTitle=False, fontSize=9.5)],
                "labels": [props(show=False)],
                "lineStyles": [
                    props(strokeWidth=2.0, showMarker=True, markerSize=4.0),
                    props(serie(reel), markerShape="circle"),
                    props(serie(prevu), lineStyle="dashed", markerShape="diamond", markerSize=8.0, strokeWidth=3.0),
                    props(serie(haut), lineStyle="dotted", markerShape="triangle", markerSize=6.0),
                    props(serie(bas), lineStyle="dotted", markerShape="square", markerSize=5.0)],
                "dataPoint": [props(serie(reel), fill=GRIS), props(serie(prevu), fill=ANTHRACITE),
                              props(serie(haut), fill=GRIS), props(serie(bas), fill=GRIS)],
            }, tri=(date, "Ascending"), alt=mes("Prévision valeur"))
        self.rectangle("prevision_fond", (x, y + h - note, w, note), ANTHRACITE)
        self.calcule("prevision_note", (x + 16, y + h - note + 8, w - 300, note - 10), mes("Prévision valeur"), 11.5,
                     JAUNE, gras=True, sous_titre=mes("Prévision méthode"), taille_sous=9.5, encre_sous=BLANC)
        self.calcule("prevision_simulation", (x + w - 280, y + h - note + 18, 264, 28), mes("Mention simulation"), 9.5,
                     JAUNE, gras=True, alignement="right")


def axe(titre: str | None = None, **kw) -> list:
    base = {"show": True, "showAxisTitle": bool(titre), "fontSize": 10.5, "labelColor": ANTHRACITE, **kw}
    if titre:
        base.update(titleText=titre, titleFontSize=10.5, titleColor=GRIS_TEXTE)
    return [props(**base)]


def sans_axe(**kw) -> list:
    return [props(show=False, showAxisTitle=False, gridlineShow=False, **kw)]


# ---------------------------------------------------------------- pages
def synthese() -> Page:
    p = Page("synthese")
    p.entete()
    p.cartes([("Livrables à valider", "À valider"), ("Livrables à traiter", "À traiter"),
              ("Citations sans source après approbation", "Sans source après approbation"),
              ("Délai de validation", None)])
    p.recommandations((X0, HAUT_CORPS, LC, HAUT_RECOS), None, "Recommandations prioritaires")
    p.prevision((X0, HAUT_SUITE, LC, BAS - HAUT_SUITE))
    return p


def production() -> Page:
    p = Page("production")
    p.entete()
    p.cartes([("Livrables à traiter", "À traiter"), ("Phrases bloquantes à corriger", "Phrases bloquantes"),
              ("Sections acceptées sans retouche", "Acceptées sans retouche")])
    p.recommandations((X0, HAUT_CORPS, LC, HAUT_RECOS), CONSULTANT, "Recommandations au consultant")
    gauche, droite = 744, LC - 744 - G
    p.tableau("a_traiter", (X0, HAUT_SUITE, gauche, BAS - HAUT_SUITE), col("Livrables", "Livrable"),
              [("À traiter état", "État"), ("À traiter motif", "Motif du renvoi"),
               ("À traiter bloquantes", "Bloquantes"), ("À traiter inactivité", "Inactif")],
              "Brouillons et renvois", "Les plus anciens d'abord",
              (mes("À traiter inactivité"), "Descending"), rangs=2.0,
              fonds={"À traiter bloquantes": "Couleur de correction"})
    p.tableau("sections", (X0 + gauche + G, HAUT_SUITE, droite, BAS - HAUT_SUITE),
              col("Sections courantes", "Section à revoir"),
              [("Section refus", "À faire"), ("Section bloquantes", "Bloquantes"), ("Section priorité", "Priorité")],
              "Sections à revoir", "Les plus urgentes d'abord",
              (mes("Section priorité"), "Descending"), rangs=2.0)
    return p


def validation() -> Page:
    p = Page("validation")
    p.entete()
    p.cartes([("Livrables à valider", "À valider"), ("Délai de validation", None),
              ("Renvois à la première relecture", "Renvois en 1re relecture"),
              ("Phrases bloquantes à vérifier", "Phrases bloquantes")])
    p.recommandations((X0, HAUT_CORPS, LC, HAUT_RECOS), RESPONSABLE, "Recommandations au responsable")
    gauche, droite = 808, LC - 808 - G
    p.tableau("file", (X0, HAUT_SUITE, gauche, BAS - HAUT_SUITE), col("Livrables", "Livrable"),
              [("File consultant", "Consultant"), ("File attente", "Attente"), ("File bloquantes", "Bloquantes"),
               ("File risque", "Risque de renvoi"), ("File priorité", "Priorité")],
              "File de validation", "En rouge : en retard",
              (mes("File priorité"), "Descending"), rangs=1.0,
              fonds={"File attente": "Couleur d'attente", "File bloquantes": "Couleur de blocage"})
    personne = col("Personnes", "Consultant")
    attente, chez_lui = mes("Charge en relecture"), mes("Charge chez le consultant")
    p.graphique("charge", "barChart", (X0 + gauche + G, HAUT_SUITE, droite, BAS - HAUT_SUITE),
                {"Category": [personne], "Y": [(attente, "En relecture"), (chez_lui, "Chez le consultant")]},
                "Charge par consultant", "Livrables ouverts",
                {"categoryAxis": axe(maxMarginFactor=45, gridlineShow=False, fontSize=9.5),
                 "valueAxis": sans_axe(start=0.0),
                 "legend": [props(show=True, position="Top", showTitle=False, fontSize=9.5)],
                 "labels": [props(show=True, fontSize=9.5, color=BLANC, labelPosition="InsideCenter")],
                 "dataPoint": [props(serie(attente), fill=ANTHRACITE), props(serie(chez_lui), fill=GRIS)]},
                tri=(personne, "Ascending"))
    return p


def administration() -> Page:
    p = Page("administration")
    p.entete()
    p.cartes([("Phrases vérifiées", "Phrases vérifiées"),
              ("Citations sans source avant relecture", "Sans source avant relecture"),
              ("Alertes d'injection", "Consignes cachées"), ("Documents signalés", None)])
    config = col("Banc", "Configuration")
    bas_banc = HAUT_CORPS + 256
    p.tableau("banc", (X0, HAUT_CORPS, LC, bas_banc - HAUT_CORPS), (config, "Configuration"),
              [("Banc montage", "Montage"), ("Banc effectif", "Sections"), ("Banc TPV", "Phrases vérifiées"),
               ("Banc écart", "Écart à B, points"), ("Banc latence", "Temps de réponse"),
               ("Banc verdict", "Décision")],
              "Banc d'essai", "Hors production, sans filtre",
              (config, "Ascending"), rangs=5.0, encres={"Banc verdict": "Couleur de décision"})
    haut = bas_banc + G
    (x1, w), (x2, _) = colonnes(2)
    p.tableau("formats", (x1, haut, w, BAS - haut), col("Documents", "Format"),
              [("Documents analysés", "Documents"), ("Nombre de documents signalés", "Signalés"),
               ("Format taux", "Part signalée")],
              "Signalements par format", "Filtre client seulement",
              (col("Documents", "Format"), "Ascending"), rangs=3.0)
    p.tableau("missions", (x2, haut, w, BAS - haut), col("Missions", "Mission"),
              [("Mission signalée", "Alertes"), ("Mission documents", "Documents de la mission")],
              "Missions signalées", "Les plus touchées d'abord",
              (mes("Mission signalée"), "Descending"), rangs=2.0)
    return p


def impression() -> Page:
    p = Page("impression", largeur=A4_L, hauteur=A4_H, barre=False)
    for i, groupe in enumerate(SEGMENTS):
        # Segments masqués : la page suit les filtres des autres pages sans les imprimer.
        p.segment(groupe, (40 + i * 200, 0, 180, 40), masque=True)
    x, w = 52, A4_L - 104
    p.rectangle("titre_filet", (x, 52, 8, 44), JAUNE)
    p.texte("titre", (x + 22, 46, 500, 56), "Rapport de pilotage", 22, ANTHRACITE, gras=True)
    p.bouton("retour", (A4_L - 52 - 120, 56, 120, 34), "←  Synthèse", "synthese", fond=FOND, encre=GRIS_TEXTE,
             survol=GRIS_CLAIR, taille=10.0, alignement="center")
    p.calcule("filtres", (x, 110, w, 40), mes("Filtres du rapport"), 9.5, GRIS_TEXTE)
    p.texte("interne", (x, 150, 420, 26), "Interne au cabinet", 10, ANTHRACITE, gras=True)
    p.calcule("simulation", (x + 420, 154, w - 420, 26), mes("Mention simulation"), 10, ROUGE, gras=True,
              alignement="right")

    def titre(nom: str, y: float, texte: str) -> None:
        p.texte(f"t_{nom}", (x, y, w, 28), texte, 13, ANTHRACITE, gras=True)
        p.rectangle(f"f_{nom}", (x, y + 29, w, 3), JAUNE)

    titre("constat", 200, "Constat")
    p.calcule("constat", (x, 242, w, 36), mes("Constat synthese"), 11.5, ANTHRACITE, gras=True)

    p.recommandations((x, 300, w, 210), None, "Recommandations prioritaires")

    def lignes(nom: str, y: float, contenu: list[tuple[str, str]], pas: float) -> None:
        for i, (libelle, mesure) in enumerate(contenu):
            haut = y + i * pas
            p.texte(f"{nom}{i}_l", (x, haut, 330, 24), libelle, 9.5, GRIS_TEXTE)
            p.calcule(f"{nom}{i}_v", (x + 334, haut + 2, w - 334, pas - 2), mes(mesure), 9.5, ANTHRACITE, gras=True)

    titre("h7", 548, "Critères de réussite")
    lignes("h7", 590, [("Citations sans source après approbation", "H7 citations"),
                       ("Sections acceptées sans retouche", "H7 retouche")], 44)

    titre("kpi", 704, "Indicateurs")
    lignes("kpi", 746, [("Livrables à valider", "Rapport file"),
                        ("Délai de validation", "Rapport délai"),
                        ("Renvois en première relecture", "Rapport renvois"),
                        ("Phrases bloquantes", "Rapport bloquantes"),
                        ("Phrases vérifiées à la génération", "Rapport vérifiées"),
                        ("Citations sans source avant relecture", "Rapport détectées")], 32)

    titre("prediction", 966, "Charge de relecture à 2 semaines")
    p.calcule("prevision", (x, 1008, w, 70), mes("Prévision valeur"), 11, ANTHRACITE, gras=True,
              sous_titre=mes("Prévision méthode"), taille_sous=9.5)

    titre("limites", 1110, "Limites")
    for i, ligne in enumerate([
        "Une source qui existe ne prouve pas qu'elle soutient la phrase.",
        "File, recommandations et prévision ne suivent pas la période.",
    ]):
        p.texte(f"limite{i}", (x, 1152 + i * 26, w, 24), "•  " + ligne, 9, GRIS_TEXTE)
    return p


# ---------------------------------------------------------------- écriture
def ecrire_json(chemin: Path, objet) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(objet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def construire_rapport(racine: Path, theme: Path) -> None:
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
    for p in (synthese(), production(), validation(), administration(), impression()):
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
