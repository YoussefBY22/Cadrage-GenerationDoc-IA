"""Rapport PBIR par acteur : quatre pages visibles et une page imprimable masquée.

Règles de conception, avec leurs sources, dans docs/14 §6 :
- titres nominaux ; sous-titre périmètre, mesure, période ; le message vit dans une zone « Constat » ;
- titres de visuels neutres, tous à la même taille ;
- au plus 4 KPI par page, en mesures numériques (épinglables avec alerte dans le Service) ;
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
    KPIS,
    RESPONSABLE,
    ROUGE,
    SUFFIXE,
    TOUS,
    TOUT,
    pilotage,
)
from pbir import CHAQUE_POINT, DEFAUT, SCHEMA, SCHEMA_VISUEL, SEMIBOLD, col, mes, props, ref, requete, serie

L, H, BARRE = 1600, 900, 256
A4_L, A4_H = 900, 1273
X0, LC, G = 288, 1280, 16
BAS = H - 24
HAUT_CORPS = 354
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
DEFINITIONS = {k.nom: k for k in KPIS}
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
            self.kpi(i, (x, 186, w, 152), nom, titre)

    def kpi(self, i: int, boite: tuple, indicateur: str, titre: str | None) -> None:
        x, y, w, h = boite
        k = DEFINITIONS[indicateur]
        titre = titre or indicateur
        conteneur = {
            "title": [props(show=True, text=titre, fontSize=TITRE_VISUEL, titleWrap=True)],
            "subTitle": [props(show=True, text=mes(f"Note {indicateur}"), fontSize=10.0, fontColor=GRIS_TEXTE,
                               titleWrap=True)],
            "padding": [props(top=8.0, bottom=0.0, left=16.0, right=8.0)],
            "visualHeaderTooltip": [props(type="Default", text=k.description, titleFontColor=ANTHRACITE)],
            "visualHeader": [props(show=True, showTooltipButton=True)],
            **alternatif(f"{titre}. Formule : {k.formule} Décision : {k.decision}."),
        }
        self.poser(f"kpi{i}", "cardVisual", (x, y, w, h - 30), req=requete({"Data": [mes(indicateur)]}),
                   conteneur=conteneur, objets={
            "layout": [props(maxTiles=1), props(DEFAUT, backgroundShow=False, paddingUniform=0, cellPadding=0)],
            "value": [props(DEFAUT, fontSize=28.0, fontColor=ANTHRACITE, fontFamily=SEMIBOLD, showBlankAs="Non mesuré",
                            labelDisplayUnits=1.0, horizontalAlignment="left")],
            "label": [props(DEFAUT, show=False)], "outline": [props(DEFAUT, show=False)],
            "fillCustom": [props(DEFAUT, show=False)],
            "padding": [props(DEFAUT, paddingUniform=0, paddingIndividual=False)],
        })
        self.rectangle(f"kpi{i}_bande", (x, y + h - 30, w, 30), ANTHRACITE)
        self.texte(f"kpi{i}_decision", (x + 16, y + h - 30, w - 20, 30), "Décision : " + k.decision, 9.5, BLANC)

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
                tri: tuple, *, rangs: float = 4.0, fonds: dict | None = None, encres: dict | None = None) -> None:
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
        }, tri)

    def recommandations(self, boite: tuple, acteur: str | None, titre: str) -> None:
        x, y, w, h = boite
        self.texte("recos_titre", (x, y, w, 28), titre, TITRE_VISUEL, ANTHRACITE, gras=True)
        n = pilotage.MAX_RECOMMENDATIONS
        hauteur = (h - 32 - 10 * (n - 1)) / n
        suffixe = SUFFIXE[acteur]
        for i in range(n):
            haut = y + 32 + i * (hauteur + 10)
            self.rectangle(f"reco{i + 1}_filet", (x, haut, 5, hauteur), JAUNE if i == 0 else GRIS_CLAIR)
            self.calcule(f"reco{i + 1}", (x + 5, haut, w - 5, hauteur), mes(f"Reco {i + 1} constat{suffixe}"),
                         11.5, ANTHRACITE, gras=True, sous_titre=mes(f"Reco {i + 1} action{suffixe}"),
                         taille_sous=10, fond=BLANC, marge=12)

    def prevision(self, boite: tuple) -> None:
        """Série régulière par quinzaine, prévision et bornes : des formes de point, pas seulement des couleurs."""
        x, y, w, h = boite
        note = 118
        reel, prevu = mes("Soumissions réelles"), mes("Prévision")
        bas, haut = mes("Borne basse"), mes("Borne haute")
        date = col("Série de prévision", "Fin de quinzaine")
        self.graphique(
            "prevision", "lineChart", (x, y, w, h - note),
            {"Category": [date],
             "Y": [(reel, "Réel"), (prevu, "Prévision"), (haut, "Borne haute"), (bas, "Borne basse")]},
            "Soumissions en relecture, par quinzaine", "Historique, puis prévision à 2 semaines et son intervalle", {
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
        self.calcule("prevision_note", (x + 16, y + h - note + 10, w - 28, 76), mes("Prévision valeur"), 11.5, JAUNE,
                     gras=True, sous_titre=mes("Prévision méthode"), taille_sous=9.5, encre_sous=BLANC)
        self.calcule("prevision_simulation", (x + 16, y + h - 26, w - 28, 24), mes("Mention simulation"), 9.5, JAUNE,
                     gras=True)


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
    p.cartes([("Livrables à valider", None), ("Livrables à traiter", None),
              ("Citations sans source après approbation", "Sans source après approbation"),
              ("Délai de validation", None)])
    gauche = 616
    p.recommandations((X0, HAUT_CORPS, gauche, BAS - HAUT_CORPS), None, "Recommandations prioritaires")
    p.prevision((X0 + gauche + G, HAUT_CORPS, LC - gauche - G, BAS - HAUT_CORPS))
    return p


def production() -> Page:
    p = Page("production")
    p.entete()
    p.cartes([("Livrables à traiter", None), ("Phrases bloquantes à corriger", "Phrases bloquantes"),
              ("Sections acceptées sans retouche", "Acceptées sans retouche")])
    gauche, droite = 808, LC - 808 - G
    p.tableau("a_traiter", (X0, HAUT_CORPS, gauche, 254), col("Livrables", "Livrable"),
              [("À traiter état", "État"), ("À traiter motif", "Motif du renvoi"),
               ("À traiter bloquantes", "Bloquantes"), ("À traiter sans preuve", "Sans preuve"),
               ("À traiter inactivité", "Inactif")],
              "Brouillons et renvois", "Par durée d'inactivité · motif détaillé dans l'application",
              (mes("À traiter inactivité"), "Descending"), rangs=2.0,
              fonds={"À traiter bloquantes": "Couleur de correction"})
    haut = HAUT_CORPS + 254 + G
    p.tableau("sections", (X0, haut, gauche, BAS - haut), col("Sections courantes", "Section à revoir"),
              [("Section refus", "À faire"), ("Section bloquantes", "Bloquantes"),
               ("Section sans source", "Sans source"), ("Section priorité", "Priorité")],
              "Sections à revoir", "Priorité : source absente (5), autre blocage (3), refus faute de preuve (2)",
              (mes("Section priorité"), "Descending"), rangs=2.0)
    p.recommandations((X0 + gauche + G, HAUT_CORPS, droite, BAS - HAUT_CORPS), CONSULTANT,
                      "Recommandations au consultant")
    return p


def validation() -> Page:
    p = Page("validation")
    p.entete()
    p.cartes([("Livrables à valider", None), ("Délai de validation", None),
              ("Renvois à la première relecture", "Renvois en 1re relecture"),
              ("Phrases bloquantes à vérifier", "Bloquantes à vérifier")])
    gauche, droite = 824, LC - 824 - G
    p.tableau("file", (X0, HAUT_CORPS, gauche, 340), col("Livrables", "Livrable"),
              [("File consultant", "Consultant"), ("File attente", "Attente"), ("File bloquantes", "Bloquantes"),
               ("File risque", "Risque de renvoi [80 %], n"), ("File priorité", "Priorité")],
              "File de validation",
              f"Priorité = jours d'attente × (1 + risque) · fond rouge : plus de {pilotage.REVIEW_OVERDUE_HOURS} h",
              (mes("File priorité"), "Descending"), rangs=1.0,
              fonds={"File attente": "Couleur d'attente", "File bloquantes": "Couleur de blocage"})
    haut = HAUT_CORPS + 340 + 10
    personne = col("Personnes", "Consultant")
    attente, chez_lui = mes("Charge en relecture"), mes("Charge chez le consultant")
    p.graphique("charge", "barChart", (X0, haut, gauche, BAS - haut),
                {"Category": [personne], "Y": [(attente, "En relecture"), (chez_lui, "Chez le consultant")]},
                "Charge par consultant", "Livrables ouverts, par ordre alphabétique (ce n'est pas un classement)",
                {"categoryAxis": axe(maxMarginFactor=40, gridlineShow=False, fontSize=9.5),
                 "valueAxis": sans_axe(start=0.0),
                 "legend": [props(show=True, position="Right", showTitle=False, fontSize=9.5)],
                 "labels": [props(show=True, fontSize=9.5, color=BLANC, labelPosition="InsideCenter")],
                 "dataPoint": [props(serie(attente), fill=ANTHRACITE), props(serie(chez_lui), fill=GRIS)]},
                tri=(personne, "Ascending"))
    x = X0 + gauche + G
    p.recommandations((x, HAUT_CORPS, droite, BAS - HAUT_CORPS - 72), RESPONSABLE, "Recommandations au responsable")
    p.calcule("risque", (x, BAS - 62, droite, 62), mes("Prévision risque"), 9.5, GRIS_TEXTE,
              sous_titre=mes("Mention simulation"), taille_sous=9.5)
    return p


def administration() -> Page:
    p = Page("administration")
    p.entete()
    p.cartes([("Phrases vérifiées", "Phrases vérifiées"),
              ("Citations sans source avant relecture", "Sans source avant relecture"),
              ("Alertes d'injection", None), ("Documents signalés", None)])
    config = col("Banc", "Configuration")
    p.tableau("banc", (X0, HAUT_CORPS, LC, 250), (config, "Config."),
              [("Banc montage", "Montage"), ("Banc effectif", "n"), ("Banc TPV", "TPV [IC 95 %]"),
               ("Banc écart", "Écart à B, points [IC 95 %]"), ("Banc citations", "Citations valides"),
               ("Banc chiffres", "Chiffres fidèles"), ("Banc attaque", "Attaques réussies"),
               ("Banc latence", "Réponse p95"), ("Banc verdict", "Décision")],
              "Banc d'essai des configurations",
              "Sections appariées, hors production, aucun filtre · A : sans recherche · B : référence · "
              "C : B + LoRA, même base · D : autre taille",
              (config, "Ascending"), rangs=5.0, encres={"Banc verdict": "Couleur de décision"})
    haut = HAUT_CORPS + 250 + G
    (x1, w), (x2, _), (x3, _) = colonnes(3)
    # Un sous-titre est coupé à trois lignes : la règle s'écrit ligne à ligne
    p.rectangle("regle_fond", (x1, haut, w, BAS - haut), BLANC)
    p.texte("regle_titre", (x1 + 16, haut + 10, w - 24, 28), "Règle de décision du banc", TITRE_VISUEL, ANTHRACITE,
            gras=True)
    for i, (ligne, gras) in enumerate([
        ("Retenir une configuration seulement si :", False),
        ("1. l'intervalle à 95 % de l'écart de TPV avec B", True),
        ("    est au-dessus de 0 (bootstrap apparié) ;", True),
        ("2. aucune sécurité ne se dégrade :", True),
        ("    citations, chiffres, attaques, refus manqués.", False),
        ("Un écart non concluant ne change rien.", False),
    ]):
        p.texte(f"regle{i}", (x1 + 16, haut + 48 + i * 30, w - 24, 26), ligne, 10.5,
                ANTHRACITE if gras else GRIS_TEXTE, gras=gras)
    p.tableau("formats", (x2, haut, w, BAS - haut), col("Documents", "Format"),
              [("Documents analysés", "n"), ("Nombre de documents signalés", "Signalés"), ("Format taux", "Taux")],
              "Signalements par format", f"Filtre client seulement · pas de taux sous {pilotage.MIN_SAMPLE}",
              (col("Documents", "Format"), "Ascending"), rangs=3.0)
    p.tableau("missions", (x3, haut, w, BAS - haut), col("Missions", "Mission"),
              [("Mission signalée", "Alertes"), ("Mission documents", "Documents")],
              "Missions signalées", "Au moins une alerte d'injection",
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
    p.calcule("simulation", (x, 150, w, 24), mes("Mention simulation"), 11, ROUGE, gras=True)

    def titre(nom: str, y: float, texte: str) -> None:
        p.texte(f"t_{nom}", (x, y, w, 28), texte, 13, ANTHRACITE, gras=True)
        p.rectangle(f"f_{nom}", (x, y + 29, w, 3), JAUNE)

    titre("constat", 182, "Constat")
    p.calcule("constat", (x, 220, w, 48), mes("Constat synthese"), 11, ANTHRACITE)

    titre("priorites", 270, "Recommandations prioritaires")
    for i in range(pilotage.MAX_RECOMMENDATIONS):
        p.calcule(f"reco{i + 1}", (x, 310 + i * 78, w, 76), mes(f"Reco {i + 1} constat"), 11, ANTHRACITE, gras=True,
                  sous_titre=mes(f"Reco {i + 1} action"), taille_sous=9.5)

    def lignes(nom: str, y: float, contenu: list[tuple[str, str]], pas: float) -> None:
        for i, (libelle, mesure) in enumerate(contenu):
            haut = y + i * pas
            p.texte(f"{nom}{i}_l", (x, haut, 310, 24), libelle, 9.5, GRIS_TEXTE)
            p.calcule(f"{nom}{i}_v", (x + 314, haut + 2, w - 314, pas - 2), mes(mesure), 9.5, ANTHRACITE, gras=True)

    titre("h7", 548, "Critères de réussite (hypothèse H7)")
    lignes("h7", 586, [("Citations sans source après approbation", "H7 citations"),
                       ("Sections acceptées sans retouche", "H7 retouche")], 42)

    titre("kpi", 714, "Indicateurs")
    lignes("kpi", 752, [("Livrables à valider", "Rapport file"),
                        ("Délai de validation", "Rapport délai"),
                        ("Renvois à la première relecture", "Rapport renvois"),
                        ("Phrases bloquantes", "Rapport bloquantes"),
                        ("Phrases vérifiées à la génération", "Rapport vérifiées"),
                        ("Citations sans source avant relecture", "Rapport détectées")], 28)

    titre("prediction", 926, "Prédiction de la charge de relecture à 2 semaines")
    p.calcule("prevision", (x, 964, w, 100), mes("Prévision valeur"), 11, ANTHRACITE, gras=True,
              sous_titre=mes("Prévision méthode"), taille_sous=9.5)

    titre("limites", 1066, "Limites")
    for i, ligne in enumerate([
        "Sans retouche : mesuré par section, alors que H7 raisonne par phrase.",
        "Une source qui existe ne prouve pas qu'elle soutient la phrase.",
        "Une phrase modifiée n'est pas revérifiée ici : seule sa source est contrôlée.",
        "File, recommandations et prédiction ne suivent pas la période.",
        "Document interne, multi-client. Pour un client : python -m app.dw.report --audience client.",
        "L'export PDF de Desktop ignore cette page masquée : utiliser la commande ci-dessus (bi/PUBLICATION.md).",
    ]):
        p.texte(f"limite{i}", (x, 1102 + i * 22, w, 22), "•  " + ligne, 9, GRIS_TEXTE)
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
