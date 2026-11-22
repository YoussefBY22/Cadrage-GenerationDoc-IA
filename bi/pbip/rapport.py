"""Rapport PBIR : une page d'accueil et quatre pages thématiques, une question de pilotage chacune.

Grille 1600 × 900 : barre latérale de 256 px, contenu de 288 à 1568 px, gouttière de 16 px.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from indicateurs import ANTHRACITE, CIBLE_REUTILISABLE, CIBLE_TEMPS, GRIS, GRIS_CLAIR, JAUNE, KPIS, ROUGE
from pbir import CHAQUE_POINT, DEFAUT, SCHEMA, SCHEMA_VISUEL, SEMIBOLD, categorie, col, mes, props, ref, requete, serie

L, H, BARRE = 1600, 900, 256
X0, LC, G = 288, 1280, 16
BAS = H - 24
BLANC, FOND, BARRE_2 = "#FFFFFF", "#F6F6FA", "#3C3C48"
THEME_BASE = "CY26SU02"

PAGES = {
    "accueil": ("Accueil", "L'assistant tient-il ses promesses ?"),
    "qualite": ("Qualité et preuves", "Peut-on se fier à ce que l'assistant écrit ?"),
    "productivite": ("Productivité et relecture", "Fait-il gagner du temps au consultant ?"),
    "modeles": ("Comparaison des modèles", "Quelle configuration faut-il retenir ?"),
    "securite": ("Sécurité et usage", "Est-il utilisé, et sans danger ?"),
}
SEGMENTS = [  # groupe de synchronisation, libellé, champ
    ("periode", "Période", col("Calendrier", "Mois")),
    ("client", "Client", col("Missions", "Client")),
    ("type", "Type de livrable", col("Types de livrable", "Type de livrable")),
    ("modele", "Modèle", col("Configurations", "Configuration et modèle")),
]
DEFINITIONS = {k.nom: k.description for k in KPIS}
# Ces visuels réduisent leurs polices en mode « responsive » : on le coupe pour garder des libellés lisibles.
RESPONSIVES = ("barChart", "clusteredBarChart", "clusteredColumnChart", "waterfallChart", "scatterChart")


def colonnes(n: int, largeur: int = LC, x0: int = X0) -> list[tuple[float, float]]:
    """n colonnes égales séparées par la gouttière : [(x, largeur), …]."""
    w = (largeur - G * (n - 1)) / n
    return [(x0 + i * (w + G), w) for i in range(n)]


class Page:
    def __init__(self, pid: str):
        self.id = pid
        self.titre, self.question = PAGES[pid]
        self.visuels: list[dict] = []
        self.barre_laterale()

    # ------------------------------------------------------------ primitives
    def poser(self, nom: str, vtype: str, boite: tuple, *, req: dict | None = None, objets: dict | None = None,
              conteneur: dict | None = None, synchro: str | None = None) -> None:
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
        self.visuels.append({
            "$schema": SCHEMA_VISUEL, "name": f"{self.id}_{nom}",
            "position": {"x": round(x, 2), "y": round(y, 2), "z": rang * 100, "width": round(w, 2),
                         "height": round(h, 2), "tabOrder": rang * 100},
            "visual": visuel})

    @staticmethod
    def nu(**autres) -> dict:
        """Conteneur sans fond, titre, bordure ni en-tête : pour les éléments de décor."""
        base = {"background": [props(show=False)], "title": [props(show=False)], "border": [props(show=False)],
                "visualHeader": [props(show=False)],
                "padding": [props(top=0.0, bottom=0.0, left=0.0, right=0.0)]}
        return {**base, **autres}

    def rectangle(self, nom: str, boite: tuple, fond: str, forme: str = "rectangle") -> None:
        self.poser(nom, "shape", boite, conteneur=self.nu(), objets={
            "shape": [props(tileShape=forme)],
            "fill": [props(show=True), props(DEFAUT, fillColor=fond, transparency=0.0)],
            "outline": [props(show=False)]})

    def texte(self, nom: str, boite: tuple, texte: str, taille: float, encre: str, gras: bool = False,
              alignement: str = "left") -> None:
        # Une forme, et non une zone de texte : celle-ci affiche des barres de défilement dès qu'elle est juste.
        self.poser(nom, "shape", boite, conteneur=self.nu(), objets={
            "shape": [props(tileShape="rectangle")], "fill": [props(show=False)], "outline": [props(show=False)],
            "text": [props(show=True), props(
                DEFAUT, text=texte, fontSize=float(taille), fontColor=encre,
                fontFamily=SEMIBOLD if gras else "Segoe UI", horizontalAlignment=alignement,
                verticalAlignment="middle", leftMargin=0, rightMargin=0, topMargin=0, bottomMargin=0)]})

    def bouton(self, nom: str, boite: tuple, texte: str, lien: dict, fond: str, encre: str, survol: str,
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
        }, conteneur=self.nu(visualLink=[props(show=True, **lien)]))

    # ------------------------------------------------------------ éléments communs
    def barre_laterale(self) -> None:
        self.rectangle("barre", (0, 0, BARRE, H), ANTHRACITE)
        self.rectangle("logo_carre", (24, 30, 30, 30), JAUNE)
        self.texte("logo_mot", (66, 20, 180, 50), "Cadrage", 22, BLANC, gras=True)
        self.texte("logo_legende", (24, 72, 220, 24), "Pilotage de l'assistant IA", 10.5, GRIS_CLAIR)

        for i, (pid, (titre, _)) in enumerate(PAGES.items()):
            active = pid == self.id
            self.bouton(f"nav_{pid}", (0, 120 + i * 48, BARRE, 44), titre,
                        {"type": "PageNavigation", "navigationSection": pid, "tooltip": f"Aller à : {titre}"},
                        fond=JAUNE if active else ANTHRACITE, encre=ANTHRACITE if active else BLANC,
                        survol=JAUNE if active else BARRE_2, gras=active)

        self.rectangle("separateur", (24, 376, BARRE - 48, 1), GRIS)
        self.texte("filtres", (24, 392, 220, 24), "FILTRES · TOUTES LES PAGES", 9.5, GRIS_CLAIR, gras=True)
        for i, (groupe, libelle, champ) in enumerate(SEGMENTS):
            self.poser(
                f"segment_{groupe}", "slicer", (16, 424 + i * 84, BARRE - 32, 76),
                req=requete({"Values": [champ]}), synchro=groupe,
                objets={
                    "data": [props(mode="Dropdown")],
                    "selection": [props(selectAllCheckboxEnabled=False, singleSelect=False)],
                    "header": [props(show=True, text=libelle, fontColor=BLANC, textSize=11.0)],
                    "items": [props(fontColor=BLANC, background=BARRE_2, textSize=11.0)],
                },
                conteneur={"background": [props(show=False)], "title": [props(show=False)],
                           "visualHeader": [props(show=False)], "border": [props(show=False)],
                           "padding": [props(top=2.0, bottom=2.0, left=4.0, right=4.0)]})
        self.bouton("effacer", (24, 780, BARRE - 48, 38), "Effacer les filtres", {"type": "ClearAllSlicers"},
                    fond=ANTHRACITE, encre=BLANC, survol=BARRE_2, taille=11.0, alignement="center", bord=GRIS)
        self.texte("local", (24, 848, 220, 28), "100 % local · aucune donnée client", 9.5, GRIS_CLAIR)

    def bandeau(self, y: float, sombre: bool = False) -> None:
        x = X0 + LC - 360 - (24 if sombre else 0)
        self.poser("bandeau", "shape", (x, y, 360, 30), objets={
            "shape": [props(tileShape="rectangle")], "fill": [props(show=False)], "outline": [props(show=False)],
        }, conteneur=self.nu(title=[props(show=True, text=mes("Bandeau données"), fontSize=10.0,
                                          fontColor=GRIS_CLAIR if sombre else GRIS, fontFamily=SEMIBOLD,
                                          alignment="right", titleWrap=False)]))

    def entete(self, sous_titre: str) -> None:
        self.rectangle("entete_filet", (X0, 34, 6, 44), JAUNE)
        self.texte("entete_question", (X0 + 20, 26, 900, 60), self.question, 24, ANTHRACITE, gras=True)
        self.texte("entete_sous_titre", (X0 + 20, 82, LC - 20, 30), sous_titre, 12, GRIS)
        self.bandeau(40)

    # ------------------------------------------------------------ cartes et graphiques
    def carte(self, nom: str, boite: tuple, valeur: str, titre: str, sous_titre, *, encre_sous_titre=GRIS,
              taille: float = 34.0, definition: str | None = None) -> None:
        conteneur = {
            "title": [props(show=True, text=titre, fontSize=12.0, titleWrap=True)],
            "subTitle": [props(show=True, text=sous_titre, fontSize=10.5, fontColor=encre_sous_titre,
                               titleWrap=True)],
            "padding": [props(top=12.0, bottom=6.0, left=16.0, right=8.0)],
        }
        if definition:
            conteneur["visualHeaderTooltip"] = [props(type="Default", text=definition, titleFontColor=ANTHRACITE)]
            conteneur["visualHeader"] = [props(show=True, showTooltipButton=True)]
        self.poser(nom, "cardVisual", boite, req=requete({"Data": [mes(valeur)]}), conteneur=conteneur, objets={
            "layout": [props(maxTiles=1), props(DEFAUT, backgroundShow=False, paddingUniform=0, cellPadding=0)],
            "value": [props(DEFAUT, fontSize=taille, fontColor=ANTHRACITE, fontFamily=SEMIBOLD,
                            horizontalAlignment="left")],
            "label": [props(DEFAUT, show=False)],
            "outline": [props(DEFAUT, show=False)],
            "fillCustom": [props(DEFAUT, show=False)],
            "padding": [props(DEFAUT, paddingUniform=0, paddingIndividual=False)],
        })

    def kpi(self, i: int, boite: tuple, indicateur: str, *, titre: str | None = None, suivi: str = "Suivi, sans seuil",
            definition: str | None = None) -> None:
        a_cible = indicateur in ("Phrases vérifiées", "Citations inventées", "Sections acceptées sans retouche",
                                 "Temps gagné")
        self.carte(f"kpi{i}", boite, f"Carte {indicateur}", titre or indicateur,
                   mes(f"Statut {indicateur}") if a_cible else suivi,
                   encre_sous_titre=mes(f"Couleur {indicateur}") if a_cible else GRIS,
                   definition=definition or DEFINITIONS.get(indicateur))

    def graphique(self, nom: str, vtype: str, boite: tuple, roles: dict, titre, sous_titre: str,
                  objets: dict, tri: tuple | None = None) -> None:
        if vtype in RESPONSIVES:
            objets = {**objets, "general": [props(responsive=False)]}
        self.poser(nom, vtype, boite, req=requete(roles, tri), objets=objets, conteneur={
            "title": [props(show=True, text=titre, fontSize=13.0, titleWrap=True)],
            "subTitle": [props(show=True, text=sous_titre, fontSize=10.5, fontColor=GRIS, titleWrap=True)],
            "spacing": [props(customizeSpacing=True, spaceBelowTitle=2.0, spaceBelowSubTitle=4.0,
                              spaceBelowTitleArea=6.0)],
            "padding": [props(top=12.0, bottom=10.0, left=16.0, right=16.0)],
        })


def axe(titre: str | None = None, **kw) -> list:
    base = {"show": True, "showAxisTitle": bool(titre), "fontSize": 10.5, "labelColor": ANTHRACITE, **kw}
    if titre:
        base.update(titleText=titre, titleFontSize=10.5, titleColor=GRIS)
    return [props(**base)]


def sans_axe(**kw) -> list:
    return [props(show=False, showAxisTitle=False, gridlineShow=False, **kw)]


def etiquettes(**kw) -> list:
    return [props(**{"show": True, "fontSize": 11.0, "color": ANTHRACITE, "labelDisplayUnits": 1.0, **kw})]


# ---------------------------------------------------------------- pages
def accueil() -> Page:
    p = Page("accueil")
    p.rectangle("couverture", (X0, 24, LC, 172), ANTHRACITE)
    p.rectangle("couverture_filet", (X0, 24, 8, 172), JAUNE)
    p.texte("couverture_titre", (X0 + 36, 48, 780, 58), p.question, 26, BLANC, gras=True)
    p.texte("couverture_sous_titre", (X0 + 36, 108, 780, 32),
            "Cadrage rédige des livrables de conseil cités et vérifiés, sur le serveur du client.", 12, GRIS_CLAIR)
    p.texte("couverture_note", (X0 + 36, 142, 780, 32),
            "Ce rapport le juge sur les trois critères de réussite du cahier des charges (H7).", 12, GRIS_CLAIR)
    p.bandeau(36, sombre=True)
    p.poser("verdict", "shape", (X0 + LC - 24 - 420, 84, 420, 92), objets={
        "shape": [props(tileShape="rectangle")], "fill": [props(show=False)], "outline": [props(show=False)],
    }, conteneur=p.nu(
        title=[props(show=True, text=mes("Verdict"), fontSize=22.0, fontColor=JAUNE, fontFamily=SEMIBOLD,
                     alignment="right", titleWrap=True)],
        subTitle=[props(show=True, text=mes("Détail du verdict"), fontSize=10.5, fontColor=BLANC,
                        alignment="right", titleWrap=True)]))

    p.texte("essentiel", (X0, 206, 300, 32), "L'essentiel", 14, ANTHRACITE, gras=True)
    p.texte("essentiel_note", (X0 + 300, 206, LC - 300, 32),
            "Valeur sur la période choisie, puis tendance par mois ; pointillés : cible", 10.5, GRIS,
            alignement="right")
    tendances = [
        ("Temps gagné", "Temps gagné (estimation)", CIBLE_TEMPS),
        ("Sections acceptées sans retouche", "Acceptées sans retouche", CIBLE_REUTILISABLE),
        ("Citations inventées", "Citations inventées", None),
        ("Phrases vérifiées", "Phrases vérifiées", CIBLE_REUTILISABLE),
        ("Délai de validation", "Délai de validation", None),
    ]
    for i, ((nom, titre, cible), (x, w)) in enumerate(zip(tendances, colonnes(5), strict=True), 1):
        p.kpi(i, (x, 240, w, 164), nom, titre=titre, suivi="Médiane, de la soumission à l'accord")
        objets = {
            "categoryAxis": axe(fontSize=9.5, labelColor=GRIS, gridlineShow=False),
            # Un peu d'air sous zéro pour que le point « 0 » et son étiquette ne soient pas rognés.
            "valueAxis": sans_axe(**({"start": 0.0, "end": 1.15} if cible else {"start": -3.0})),
            "general": [props(responsive=False)],
            "labels": etiquettes(fontSize=10.0, color=GRIS, enableBackground=True, backgroundColor=BLANC,
                                 backgroundTransparency=0.0),
            "lineStyles": [props(strokeWidth=2.0, showMarker=True, markerSize=5.0)],
            "dataPoint": [props(serie(mes(nom)), fill=ANTHRACITE)],
        }
        if nom == "Délai de validation":
            # Au format du modèle, trois points à « 5 h » : on affiche la valeur décimale en français.
            objets["labels"] = [props(show=True, fontSize=10.0, color=GRIS, showDynamicLabels=True,
                                      enableValueDataLabel=True),
                                props({**CHAQUE_POINT, "highlightMatching": 1},
                                      dynamicLabelValue=mes(f"Carte {nom}"))]
        if cible:
            objets["y1AxisReferenceLine"] = [props(
                {"id": "1"}, show=True, value=float(cible), displayName="Cible", lineColor=GRIS_CLAIR,
                style="dashed", width=2.0, transparency=0.0, position="back")]
        p.poser(f"tendance{i}", "lineChart", (x, 404, w, 152),
                req=requete({"Category": [col("Calendrier", "Mois abrégé")], "Y": [mes(nom)]},
                            (col("Calendrier", "Mois abrégé"), "Ascending")),
                objets=objets,
                conteneur={"title": [props(show=False)], "visualHeader": [props(show=False)],
                           "padding": [props(top=0.0, bottom=8.0, left=8.0, right=8.0)]})

    p.texte("explorer", (X0, 572, 600, 32), "Comprendre le résultat", 14, ANTHRACITE, gras=True)
    tuiles = [("qualite", "Tuile qualité"), ("productivite", "Tuile productivité"),
              ("modeles", "Tuile modèles"), ("securite", "Tuile sécurité")]
    for (pid, mesure), (x, w) in zip(tuiles, colonnes(4), strict=True):
        p.rectangle(f"tuile_filet_{pid}", (x, 608, w, 4), JAUNE)
        p.carte(f"tuile_{pid}", (x, 612, w, 220), mesure, PAGES[pid][0], PAGES[pid][1], taille=21.0)
        p.bouton(f"ouvrir_{pid}", (x, 832, w, BAS - 832), "Ouvrir la page  →",
                 {"type": "PageNavigation", "navigationSection": pid, "tooltip": f"Aller à : {PAGES[pid][0]}"},
                 fond=ANTHRACITE, encre=BLANC, survol=BARRE_2, gras=True, taille=11.0)
    return p


def qualite() -> Page:
    p = Page("qualite")
    p.entete("Chaque phrase doit citer une source qui existe, et chaque chiffre doit y figurer.")
    cartes = [("Phrases vérifiées", None, ""), ("Citations inventées", None, ""),
              ("Chiffres retrouvés dans la source", "Chiffres retrouvés", "Dans le passage cité"),
              ("Sections refusées faute de preuve", "Refus faute de preuve", "Part des sections générées")]
    for i, ((nom, titre, suivi), (x, w)) in enumerate(zip(cartes, colonnes(4), strict=True), 1):
        p.kpi(i, (x, 124, w, 150), nom, titre=titre, suivi=suivi)

    (xg, w), (xd, _) = colonnes(2)
    p.graphique("cascade", "waterfallChart", (xg, 290, w, 284),
                {"Category": [col("Cascade", "Résultat du contrôle")], "Y": [mes("Variation de phrases")]},
                mes("Titre cascade"), "Des phrases générées au total vérifié, après contrôle automatique",
                {"categoryAxis": axe(), "valueAxis": sans_axe(), "legend": [props(show=False)],
                 "labels": etiquettes(),
                 "sentimentColors": [props(increaseFill=ANTHRACITE, decreaseFill=GRIS_CLAIR, totalFill=JAUNE)]},
                tri=(col("Cascade", "Résultat du contrôle"), "Ascending"))

    gravite = col("Citations", "Gravité")
    p.graphique("anomalies", "barChart", (xg, 590, w, BAS - 590),
                {"Category": [col("Citations", "Anomalie")], "Series": [gravite], "Y": [mes("Anomalies")]},
                mes("Titre anomalies"), "Nombre de citations en anomalie, par motif et par gravité",
                {"categoryAxis": axe(maxMarginFactor=45, gridlineShow=False), "valueAxis": sans_axe(),
                 "legend": [props(show=True, position="TopRight", showTitle=False, fontSize=10.0)],
                 "labels": etiquettes(labelPosition="InsideEnd", color=BLANC),
                 "dataPoint": [props(categorie(gravite, "Bloquante"), fill=ROUGE),
                               props(categorie(gravite, "À vérifier"), fill=GRIS)]},
                tri=(mes("Anomalies"), "Descending"))

    taux = mes("Phrases vérifiées")
    p.graphique("sections", "pivotTable", (xd, 290, w, BAS - 290),
                {"Rows": [col("Générations", "Section")], "Columns": [col("Configurations", "Configuration")],
                 "Values": [taux]},
                mes("Titre sections fragiles"),
                "Phrases vérifiées par section et configuration · rouge : moins de 50 % · gris : 50 à 80 %",
                {**tableau(rangs=9.0),
                 "values": [*valeurs_tableau(),
                            props({**CHAQUE_POINT, "metadata": ref(taux)}, backColor=mes("Fond de taux"))],
                 "subTotals": [props(rowSubtotals=True, columnSubtotals=True,
                                     rowSubtotalsLabel="Ensemble", columnSubtotalsLabel="Ensemble")]},
                tri=(taux, "Ascending"))
    return p


def tableau(rangs: float) -> dict:
    return {
        "stylePreset": [props(name="None")],
        "grid": [props(rowPadding=rangs, gridHorizontal=True, gridHorizontalColor=FOND, gridVertical=False,
                       textSize=11.0, outlineColor=GRIS_CLAIR)],
        "columnHeaders": [props(fontFamily=SEMIBOLD, fontSize=10.5, fontColor=GRIS, backColor=BLANC,
                                wordWrap=True, autoSizeColumnWidth=True, columnAdjustment="growToFit",
                                alignment="Center")],
        "rowHeaders": [props(fontSize=11.0, fontColor=ANTHRACITE, showExpandCollapseButtons=False)],
    }


def valeurs_tableau() -> list:
    return [props(fontSize=11.0, fontColorPrimary=ANTHRACITE, fontColorSecondary=ANTHRACITE,
                  backColorPrimary=BLANC, backColorSecondary=BLANC)]


def productivite() -> Page:
    p = Page("productivite")
    p.entete("Le gain n'est réel que si le texte est gardé et validé vite. Temps gagné : estimation.")
    cartes = [("Temps gagné", None, ""), ("Temps gagné par livrable", "Gain par livrable", "Estimation, en heures"),
              ("Sections acceptées sans retouche", "Acceptées sans retouche", ""),
              ("Délai de validation", None, "Médiane par livrable"),
              ("Renvois en correction", None, "Part des soumissions")]
    for i, ((nom, titre, suivi), (x, w)) in enumerate(zip(cartes, colonnes(5), strict=True), 1):
        p.kpi(i, (x, 124, w, 150), nom, titre=titre, suivi=suivi)

    (xg, w), (xd, _) = colonnes(2)
    etape = col("Étapes", "Étape")
    p.graphique("entonnoir", "funnel", (xg, 290, w, 300),
                {"Category": [etape], "Y": [mes("Sections à l'étape")]},
                mes("Titre entonnoir"), "Entonnoir de validation, en nombre de sections",
                {"categoryAxis": [props(show=True, color=ANTHRACITE, fontSize=10.5)],
                 "percentBarLabel": [props(show=False)],
                 "labels": etiquettes(labelPosition="InsideCenter", funnelLabelStyle="Data", color=BLANC),
                 "dataPoint": [props(defaultColor=GRIS),
                               props(categorie(etape, "Sans retouche"), fill=ANTHRACITE)]},
                tri=(etape, "Ascending"))

    ampleur = col("Sections approuvées", "Ampleur de la retouche")
    p.graphique("retouches", "clusteredColumnChart", (xg, 606, w, BAS - 606),
                {"Category": [ampleur], "Y": [(mes("Sections rédigées puis approuvées"), "Sections")]},
                mes("Titre retouches"), "Sections approuvées selon la part de texte modifiée",
                {"categoryAxis": axe(fontSize=10.0, innerPadding=15), "valueAxis": sans_axe(start=0.0),
                 "labels": etiquettes(),
                 "dataPoint": [props(CHAQUE_POINT, fill=mes("Couleur de retouche"))]},
                tri=(ampleur, "Ascending"))

    p.graphique("reecriture", "clusteredBarChart", (xd, 290, w, BAS - 290),
                {"Category": [col("Sections approuvées", "Section")], "Y": [mes("Part réécrite")]},
                mes("Titre réécriture"), "Part moyenne du texte modifiée : les gabarits à améliorer en premier",
                {"categoryAxis": axe(maxMarginFactor=48, gridlineShow=False, innerPadding=30),
                 "valueAxis": sans_axe(start=0.0), "labels": etiquettes(labelPosition="OutsideEnd"),
                 "dataPoint": [props(CHAQUE_POINT, fill=mes("Couleur de réécriture"))]},
                tri=(mes("Part réécrite"), "Descending"))
    return p


def modeles() -> Page:
    p = Page("modeles")
    p.entete("Quatre configurations du banc d'essai, B étant la référence. Une seule sera déployée chez le client.")
    config = col("Configurations", "Configuration")
    p.graphique("criteres", "clusteredColumnChart", (X0, 124, LC, 368),
                {"Category": [config], "Y": [(mes("Valeur du critère"), "Valeur")],
                 "Rows": [col("Critères", "Critère")]},
                mes("Titre critères"), "Quatre critères de qualité, plus haut = mieux · jaune : meilleure configuration",
                {"categoryAxis": axe(gridlineShow=False), "valueAxis": sans_axe(start=0.0, end=1.15),
                 "labels": etiquettes(labelPosition="OutsideEnd"),
                 "smallMultiplesLayout": [props(layoutType="custom", columnCount=4, rowCount=1,
                                                gridLineType="inner", gridLineColor=FOND)],
                 "subheader": [props(show=True, fontSize=11.5, fontColor=ANTHRACITE, fontFamily=SEMIBOLD)],
                 "dataPoint": [props(CHAQUE_POINT, fill=mes("Couleur du critère"))]},
                tri=(config, "Ascending"))

    ecart, taux = mes("Écart à la référence B"), mes("Phrases vérifiées")
    p.graphique("bilan", "pivotTable", (X0, 508, 784, BAS - 508),
                {"Rows": [(col("Configurations", "Configuration et modèle"), "Configuration")],
                 "Values": [(mes("Générations de sections"), "Sections générées"),
                            (taux, "Phrases vérifiées"), (ecart, "Écart à B"),
                            (mes("Citations inventées"), "Citations inventées"),
                            (mes("Sections refusées faute de preuve"), "Refus"),
                            (mes("Temps de réponse p95"), "Réponse p95")]},
                mes("Titre bilan"), "Bilan par configuration ; un petit nombre de sections fragilise la comparaison",
                {**tableau(rangs=12.0),
                 "values": [*valeurs_tableau(),
                            props({**CHAQUE_POINT, "metadata": ref(ecart)}, fontColor=mes("Couleur d'écart")),
                            props({**CHAQUE_POINT, "metadata": ref(taux)}, backColor=mes("Fond de taux"))],
                 "subTotals": [props(rowSubtotals=False, columnSubtotals=False)]},
                tri=(taux, "Descending"))

    p.graphique("arbitrage", "scatterChart", (X0 + 784 + G, 508, LC - 784 - G, BAS - 508),
                {"Category": [config], "X": [mes("Temps de réponse p95")], "Y": [taux]},
                mes("Titre arbitrage"), "En haut à gauche : fiable et rapide",
                {"categoryAxis": axe("Temps de réponse p95 (secondes)", gridlineShow=False),
                 "valueAxis": axe("Phrases vérifiées", start=0.0, end=1.0, gridlineShow=True),
                 "categoryLabels": [props(show=True, fontSize=12.0, color=ANTHRACITE)],
                 "bubbles": [props(bubbleSize=10)], "legend": [props(show=False)],
                 "dataPoint": [props(defaultColor=GRIS)]})
    return p


def securite() -> Page:
    p = Page("securite")
    p.entete("Repérer les documents piégés et suivre l'adoption. Les documents ne dépendent ni du modèle ni du type.")
    cartes = [("Alertes d'injection", "À examiner une par une"), ("Documents signalés", "Part des documents importés"),
              ("Missions actives", "Avec au moins une génération"), ("Livrables approuvés", "Validés par un manager")]
    for i, ((nom, suivi), (x, w)) in enumerate(zip(cartes, colonnes(4), strict=True), 1):
        p.kpi(i, (x, 124, w, 150), nom, suivi=suivi,
              definition="Missions avec au moins une génération sur la période." if nom == "Missions actives" else None)

    (xg, w), (xd, _) = colonnes(2)
    p.graphique("alertes", "clusteredBarChart", (xg, 290, w, 300),
                {"Category": [col("Missions", "Mission")], "Y": [(mes("Alertes par mission"), "Alertes")]},
                mes("Titre alertes"), "Consignes cachées détectées ; les missions sans alerte sont masquées",
                {"categoryAxis": axe(maxMarginFactor=45, gridlineShow=False), "valueAxis": sans_axe(start=0.0),
                 "labels": etiquettes(labelPosition="InsideEnd", color=BLANC),
                 "dataPoint": [props(defaultColor=ROUGE)]},
                tri=(mes("Alertes par mission"), "Descending"))

    signales, sains = mes("Nombre de documents signalés"), mes("Documents sans alerte")
    p.graphique("formats", "barChart", (xd, 290, w, 300),
                {"Category": [col("Documents", "Format")], "Y": [(signales, "Signalés"), (sains, "Sans alerte")]},
                mes("Titre formats"), "Documents importés par format, signalés ou non",
                {"categoryAxis": axe(maxMarginFactor=30, gridlineShow=False), "valueAxis": sans_axe(start=0.0),
                 "legend": [props(show=True, position="TopRight", showTitle=False, fontSize=10.0)],
                 "labels": [*etiquettes(labelPosition="InsideCenter"), props(serie(signales), color=BLANC),
                            props(serie(sains), color=ANTHRACITE)],
                 "dataPoint": [props(serie(signales), fill=ROUGE), props(serie(sains), fill=GRIS_CLAIR)]},
                tri=(signales, "Descending"))

    mois = col("Calendrier", "Mois abrégé")
    p.graphique("usage", "clusteredColumnChart", (X0, 606, LC, BAS - 606),
                {"Category": [mois], "Y": [mes("Générations")], "Rows": [col("Missions", "Client")]},
                mes("Titre usage"), "Générations par mois, un panneau par client",
                {"categoryAxis": axe(fontSize=9.5, gridlineShow=False), "valueAxis": sans_axe(start=0.0),
                 "labels": etiquettes(fontSize=10.5, labelPosition="InsideEnd", color=BLANC),
                 "smallMultiplesLayout": [props(layoutType="custom", columnCount=5, rowCount=1,
                                                gridLineType="inner", gridLineColor=FOND)],
                 "subheader": [props(show=True, fontSize=11.0, fontColor=ANTHRACITE, fontFamily=SEMIBOLD)],
                 "dataPoint": [props(defaultColor=ANTHRACITE)]},
                tri=(mois, "Ascending"))
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
        "pageOrder": list(PAGES), "activePageName": next(iter(PAGES))})
    for p in (accueil(), qualite(), productivite(), modeles(), securite()):
        ecrire_json(d / "pages" / p.id / "page.json", {
            "$schema": f"{SCHEMA}/page/2.1.0/schema.json", "name": p.id, "displayName": p.titre,
            "displayOption": "FitToPage", "height": H, "width": L,
            "objects": {"background": [props(color=FOND, transparency=0.0)],
                        "outspace": [props(color=FOND, transparency=0.0)]}})
        for v in p.visuels:
            ecrire_json(d / "pages" / p.id / "visuals" / v["name"] / "visual.json", v)
