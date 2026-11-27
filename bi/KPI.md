# Indicateurs du tableau de bord Power BI

> Fichier généré par `python bi/pbip/build_pbip.py` depuis [`pbip/indicateurs.py`](pbip/indicateurs.py).
> Pages et visuels : [pages.md](pages.md). Qui voit quoi : [docs/14](../docs/14-acteurs-dashboard.md).

Chaque visuel qui mélange projets réels et de démonstration le dit dans son sous-titre (« [DÉMO] 1 projet réel + 5 de démonstration »). Le filtre **Données** est réglé par défaut sur « Réelles + démonstration ».

## Indicateurs

| Dossier | Indicateur | Définition | Format |
|---|---|---|---|
| Activité | **Projets** | Projets (dossiers) dans le périmètre des filtres. | `#,0` |
| Activité | **Projets de démonstration** | — | `#,0` |
| Activité | **Projets réels** | — | `#,0` |
| Activité | **Documents** | — | `#,0` |
| Activité | **Livrables** | Livrables créés dans la période. | `#,0` |
| Activité | **Brouillons** | — | `#,0` |
| Activité | **En relecture** | — | `#,0` |
| Activité | **Approuvés** | — | `#,0` |
| Activité | **Renvoyés** | — | `#,0` |
| Activité | **Constats** | — | `#,0` |
| Activité | **Constats à valider** | — | `#,0` |
| Activité | **Initiatives** | — | `#,0` |
| Activité | **Constats traités** | — | `#,0` |
| Activité | **Appels au modèle** | Chaque appel : une section, une extraction de constats, un regroupement en axes, des initiatives. | `#,0` |
| Activité | **Temps moyen par appel** | Durée moyenne d'un appel au modèle, en secondes, sur le PC local. | `0.0 "s"` |
| Qualité de l'IA | **Appels en erreur** | — | `#,0` |
| Qualité de l'IA | **Taux d'erreur de l'IA** | Part des appels avec au moins une erreur : sortie invalide, phrase non vérifiée ou citation sans source. Un refus faute de preuve est le comportement voulu : il n'est pas compté, voir Taux de refus. | `0 %` |
| Qualité de l'IA | **Phrases générées** | — | `#,0` |
| Qualité de l'IA | **Phrases vérifiées** | — | `#,0` |
| Qualité de l'IA | **Taux de phrases vérifiées** | Phrases retrouvées dans leur source par le vérificateur ÷ phrases générées. | `0 %` |
| Qualité de l'IA | **Phrases non vérifiées** | — | `#,0` |
| Qualité de l'IA | **Taux de phrases non vérifiées** | — | `0.0 %` |
| Qualité de l'IA | **Phrases à revoir** | — | `#,0` |
| Qualité de l'IA | **Citations générées** | — | `#,0` |
| Qualité de l'IA | **Citations sans source** | — | `#,0` |
| Qualité de l'IA | **Taux de citations sans source** | — | `0.0 %` |
| Qualité de l'IA | **Sections générées** | — | `#,0` |
| Qualité de l'IA | **Sections refusées** | — | `#,0` |
| Qualité de l'IA | **Taux de refus** | Sections où le modèle répond « preuves insuffisantes » ÷ sections demandées. | `0 %` |
| Qualité de l'IA | **Sorties invalides** | — | `#,0` |
| Qualité de l'IA | **Appels feuille de route** | — | `#,0` |
| Qualité de l'IA | **Erreurs** | Erreurs du type choisi (table Types d'erreur). | `#,0` |
| Recommandations des rapports | **Rapports d'audit** | — | `#,0` |
| Recommandations des rapports | **Recommandations annoncées** | Numéros « Recommandation n° … » que le rapport annonce (plus grand numéro cité). | `#,0` |
| Recommandations des rapports | **Recommandations retenues** | Version corrigée par le consultant : supprimées et fusionnées exclues. | `#,0` |
| Recommandations des rapports | **Recommandations validées** | — | `#,0` |
| Recommandations des rapports | **Recommandations à valider** | — | `#,0` |
| Recommandations des rapports | **Recommandations manquantes** | Numéros annoncés par le rapport mais absents des recommandations retenues. | `#,0` |
| Recommandations des rapports | **Rapports en alerte** | Rapports avec un écart de numérotation (trou, doublon) ou sans aucune recommandation détectée. | `#,0` |
| Entraînement | **Entraînements** | — | `#,0` |
| Entraînement | **Entraînements adoptés** | — | `#,0` |
| Entraînement | **Modèle adopté** | — | `texte` |
| Entraînement | **Meilleure erreur du modèle adopté** | — | `0.000` |
| Entraînement | **Exemples d'entraînement** | — | `#,0` |
| Entraînement | **Erreur de validation** | Erreur sur les exemples mis de côté, mesurée tous les 20 pas : elle doit baisser. | `0.000` |
| Entraînement | **Erreur au meilleur pas** | — | `0.000` |
| Entraînement | **Exemples réussis** | — | `#,0` |
| Entraînement | **Exemples testés** | — | `#,0` |
| Entraînement | **Taux de réussite** | Exemples de test réussis ÷ exemples de test, par tâche et par modèle. | `0 %` |

## Que faire ensuite : règles d'action

Règles explicites, sans modèle de langue, évaluées sur le périmètre filtré. Les 3 premières qui se déclenchent s'affichent, dans l'ordre du rang ; sinon : « Rien d'urgent : aucune règle ne se déclenche sur ce périmètre. »

| Rang | Action | Pour | Se déclenche quand |
|---:|---|---|---|
| 1 | Contrôler les recommandations | Consultant | au moins un rapport en alerte (trou ou doublon de numérotation, ou aucune recommandation détectée) |
| 2 | Relancer la feuille de route | Consultant | sorties invalides ≥ 10% des appels « axes » et « initiatives » |
| 3 | Revoir les sources | Consultant | phrases non vérifiées ≥ 10% ; la section désignée a au moins 10 phrases |
| 4 | Compléter les documents | Consultant | sections refusées ≥ 20% des sections demandées |
| 5 | Relire | Responsable | au moins un livrable en relecture |
| 6 | Reprendre les renvois | Consultant | au moins un livrable renvoyé |
| 7 | Valider les constats | Consultant | au moins un constat non validé |

## Formules DAX

### Projets

```dax
Projets =
COUNTROWS(Projets) + 0
```

### Projets de démonstration

```dax
Projets de démonstration =
CALCULATE(COUNTROWS(Projets), Projets[Données] = "Démonstration") + 0
```

### Projets réels

```dax
Projets réels =
CALCULATE(COUNTROWS(Projets), Projets[Données] = "Réelles") + 0
```

### Documents

```dax
Documents =
SUM(Projets[Documents]) + 0
```

### Livrables

```dax
Livrables =
COUNTROWS(Livrables)
```

### Brouillons

```dax
Brouillons =
CALCULATE(COUNTROWS(Livrables), Livrables[Code d'état] = "draft") + 0
```

### En relecture

```dax
En relecture =
CALCULATE(COUNTROWS(Livrables), Livrables[Code d'état] = "in_review") + 0
```

### Approuvés

```dax
Approuvés =
CALCULATE(COUNTROWS(Livrables), Livrables[Code d'état] = "approved") + 0
```

### Renvoyés

```dax
Renvoyés =
CALCULATE(COUNTROWS(Livrables), Livrables[Code d'état] = "rejected") + 0
```

### Constats

```dax
Constats =
COUNTROWS(Constats)
```

### Constats à valider

```dax
Constats à valider =
CALCULATE(COUNTROWS(Constats), Constats[Validé] = 0) + 0
```

### Initiatives

```dax
Initiatives =
COUNTROWS(Initiatives)
```

### Constats traités

```dax
Constats traités =
SUM(Initiatives[Constats traités])
```

### Appels au modèle

```dax
Appels au modèle =
COUNTROWS('Générations')
```

### Temps moyen par appel

```dax
Temps moyen par appel =
DIVIDE(AVERAGE('Générations'[Durée en ms]), 1000)
```

### Appels en erreur

```dax
Appels en erreur =
SUM('Générations'[En erreur]) + 0
```

### Taux d'erreur de l'IA

```dax
Taux d'erreur de l'IA =
DIVIDE([Appels en erreur], [Appels au modèle])
```

### Phrases générées

```dax
Phrases générées =
SUM('Générations'[Phrases produites]) + 0
```

### Phrases vérifiées

```dax
Phrases vérifiées =
SUM('Générations'[Phrases validées]) + 0
```

### Taux de phrases vérifiées

```dax
Taux de phrases vérifiées =
DIVIDE([Phrases vérifiées], [Phrases générées])
```

### Phrases non vérifiées

```dax
Phrases non vérifiées =
SUM('Générations'[Phrases non vérifiées]) + 0
```

### Taux de phrases non vérifiées

```dax
Taux de phrases non vérifiées =
DIVIDE([Phrases non vérifiées], [Phrases générées])
```

### Phrases à revoir

```dax
Phrases à revoir =
SUM('Générations'[Phrases à revoir]) + 0
```

### Citations générées

```dax
Citations générées =
SUM('Générations'[Citations produites]) + 0
```

### Citations sans source

```dax
Citations sans source =
SUM('Générations'[Citations produites]) - SUM('Générations'[Citations valides]) + 0
```

### Taux de citations sans source

```dax
Taux de citations sans source =
DIVIDE([Citations sans source], [Citations générées])
```

### Sections générées

```dax
Sections générées =
COUNTROWS(FILTER('Générations', NOT 'Générations'[Code de section] IN {"_findings", "_axes", "_initiatives"})) + 0
```

### Sections refusées

```dax
Sections refusées =
CALCULATE(COUNTROWS('Générations'), 'Générations'[Statut] = "refused") + 0
```

### Taux de refus

```dax
Taux de refus =
DIVIDE([Sections refusées], [Sections générées])
```

### Sorties invalides

```dax
Sorties invalides =
CALCULATE(COUNTROWS('Générations'), 'Générations'[Statut] = "invalid") + 0
```

### Appels feuille de route

```dax
Appels feuille de route =
CALCULATE(COUNTROWS('Générations'), 'Générations'[Code de section] IN {"_axes", "_initiatives"}) + 0
```

### Erreurs

```dax
Erreurs =
SWITCH(SELECTEDVALUE('Types d''erreur'[Code d'erreur]), "failed", [Phrases non vérifiées], "warning", [Phrases à revoir], "citation", [Citations sans source], "invalid", [Sorties invalides])
```

### Rapports d'audit

```dax
Rapports d'audit =
COUNTROWS(Rapports) + 0
```

### Recommandations annoncées

```dax
Recommandations annoncées =
SUM(Rapports[Annoncées]) + 0
```

### Recommandations retenues

```dax
Recommandations retenues =
CALCULATE(COUNTROWS(Recommandations), Recommandations[Active] = 1)
```

### Recommandations validées

```dax
Recommandations validées =
CALCULATE(COUNTROWS(Recommandations), Recommandations[Code du statut] = "validated")
```

### Recommandations à valider

```dax
Recommandations à valider =
CALCULATE(COUNTROWS(Recommandations), Recommandations[Code du statut] = "proposed")
```

### Recommandations manquantes

```dax
Recommandations manquantes =
SUM(Rapports[Manquantes])
```

### Rapports en alerte

```dax
Rapports en alerte =
SUM(Rapports[En alerte]) + 0
```

### Entraînements

```dax
Entraînements =
COUNTROWS('Entraînements') + 0
```

### Entraînements adoptés

```dax
Entraînements adoptés =
CALCULATE(COUNTROWS('Entraînements'), 'Entraînements'[Adopté] = 1) + 0
```

### Modèle adopté

```dax
Modèle adopté =
CALCULATE(SELECTEDVALUE('Entraînements'[Essai], "Aucun"), REMOVEFILTERS('Entraînements'), 'Entraînements'[Adopté] = 1)
```

### Meilleure erreur du modèle adopté

```dax
Meilleure erreur du modèle adopté =
CALCULATE(MIN('Entraînements'[Meilleure erreur de validation]), REMOVEFILTERS('Entraînements'), 'Entraînements'[Adopté] = 1)
```

### Exemples d'entraînement

```dax
Exemples d'entraînement =
MAX('Entraînements'[Exemples d'entraînement])
```

### Erreur de validation

```dax
Erreur de validation =
AVERAGE('Courbe de validation'[Erreur de validation])
```

### Erreur au meilleur pas

```dax
Erreur au meilleur pas =
CALCULATE([Erreur de validation], 'Courbe de validation'[Meilleur] = 1)
```

### Exemples réussis

```dax
Exemples réussis =
SUM(Scores[Réussis]) + 0
```

### Exemples testés

```dax
Exemples testés =
SUM(Scores[Total]) + 0
```

### Taux de réussite

```dax
Taux de réussite =
DIVIDE(SUM(Scores[Réussis]), SUM(Scores[Total]))
```

### Liste des actions

```dax
Liste des actions =
VAR t = FILTER({
    (1, IF([Rapports en alerte] > 0, "Contrôler " & [Rapports en alerte] & " rapport(s) d'audit " & [Portée] & " : " & [Recommandations manquantes] + 0 & " recommandation(s) manquante(s) ou non détectée(s). Page Recommandations du dossier." & "  [" & "Consultant" & "]", BLANK())),
    (2, IF(DIVIDE([Sorties invalides], [Appels feuille de route]) >= 0.1, "Relancer la feuille de route : " & [Sorties invalides] & " réponse(s) du modèle au mauvais format sur " & [Appels feuille de route] & " appels." & "  [" & "Consultant" & "]", BLANK())),
    (3, IF([Taux de phrases non vérifiées] >= 0.1, "Revoir les sources de « " & [Section la moins vérifiée] & " » : " & FORMAT([Taux de phrases non vérifiées], "0 %") & " des phrases non vérifiées sur le périmètre." & "  [" & "Consultant" & "]", BLANK())),
    (4, IF([Taux de refus] >= 0.2, "Compléter les documents : le modèle refuse " & FORMAT([Taux de refus], "0 %") & " des sections faute de preuves, surtout « " & [Section la plus refusée] & " »." & "  [" & "Consultant" & "]", BLANK())),
    (5, IF([En relecture] > 0, "Relire " & [En relecture] & " livrable(s) en attente de validation." & "  [" & "Responsable" & "]", BLANK())),
    (6, IF([Renvoyés] > 0, "Reprendre " & [Renvoyés] & " livrable(s) renvoyé(s) par le responsable." & "  [" & "Consultant" & "]", BLANK())),
    (7, IF([Constats à valider] > 0, "Valider " & [Constats à valider] & " constat(s) avant de produire la feuille de route." & "  [" & "Consultant" & "]", BLANK()))
}, NOT ISBLANK([Value2]))
RETURN IF(COUNTROWS(t) = 0, "Rien d'urgent : aucune règle ne se déclenche sur ce périmètre.", CONCATENATEX(t, [Value2], " / ", [Value1], ASC))
```
