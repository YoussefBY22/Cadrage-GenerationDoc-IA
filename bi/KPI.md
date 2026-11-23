# Indicateurs du tableau de bord Power BI

> Fichier généré par `python bi/pbip/build_pbip.py` depuis [`pbip/indicateurs.py`](pbip/indicateurs.py)
> et [`pilotage.py`](../backend/app/dw/pilotage.py), la source unique des seuils et des règles.
> Qui voit quoi : [docs/14](../docs/14-acteurs-dashboard.md).

Les pages montrent le nombre et son effectif. Décisions, formules, cibles et seuils ne vivent qu'ici.

Principes : au plus 4 indicateurs par page acteur, chacun lié à une décision ; un taux va avec son effectif et disparaît sous 30 cas ; un critère non mesuré s'affiche « non mesuré », sans verdict. Sur les données de démonstration, aucune qualité de modèle n'est mesurée.

## Consultant

### Livrables à traiter

- **Décision** : Par quel livrable commencer
- **Formule** : livrables en brouillon ou renvoyés, dont les renvois pas encore resoumis.
- **Cible** : aucun seuil dans H7
- **Portée** : Situation à la date des données : ne suit pas la période.

```dax
Livrables à traiter =
CALCULATE(COUNTROWS(Livrables), KEEPFILTERS(Livrables[Code d'état] IN {"draft", "rejected"})) + 0
```

### Phrases bloquantes à corriger

- **Décision** : Quoi corriger avant de soumettre
- **Formule** : phrases des livrables chez le consultant dont la source est absente du dossier, ou rejetées par le vérificateur et inchangées depuis.
- **Cible** : 0 avant de soumettre (règle du produit)
- **Portée** : Situation à la date des données : ne suit pas la période.
- **Limite** : une phrase modifiée n'est pas revérifiée ici : seule sa source est contrôlée.

```dax
Phrases bloquantes à corriger =
CALCULATE(SUM(Livrables[Phrases bloquantes]), KEEPFILTERS(Livrables[Code d'état] IN {"draft", "rejected"})) + 0
```

### Sections acceptées sans retouche

- **Décision** : Partir du premier jet ou le retravailler
- **Formule** : sections approuvées mot pour mot ÷ sections rédigées puis approuvées (refus exclus).
- **Cible** : au moins 50 % (H7)
- **Portée** : Flux : suit la période.
- **Limite** : H7 raisonne par phrase, l'entrepôt par section (plus sévère). Pas de taux sous 30 sections.

```dax
Sections acceptées sans retouche =
VAR vN = [Sections rédigées puis approuvées]
RETURN IF(MAX('Source des données'[Est une démonstration]) = 1, BLANK(), IF(vN >= 30, DIVIDE([Nombre de sections sans retouche], vN)))
```

## Responsable

### Livrables à valider

- **Décision** : Qui relit quoi aujourd'hui
- **Formule** : livrables en relecture, dont ceux qui attendent depuis plus de 48 h.
- **Cible** : 0 au-delà de 48 h (règle de pilotage, hors H7)
- **Portée** : Situation à la date des données : ne suit pas la période.

```dax
Livrables à valider =
CALCULATE(COUNTROWS(Livrables), KEEPFILTERS(Livrables[Code d'état] IN {"in_review"})) + 0
```

### Délai de validation

- **Décision** : Renforcer ou répartir la relecture
- **Formule** : médiane des heures entre la première soumission et l'approbation.
- **Cible** : aucun seuil dans H7
- **Portée** : Flux : suit la période.
- **Limite** : heures calendaires ; pas de valeur sous 30 livrables ; ne voit pas ce qui attend encore.

```dax
Délai de validation =
IF([Livrables avec délai] >= 30, CALCULATE(MEDIAN(Livrables[Délai en heures]), KEEPFILTERS(Livrables[Code d'état] IN {"approved"}), USERELATIONSHIP(Livrables[Clé d'approbation], Calendrier[Clé de date])))
```

### Renvois à la première relecture

- **Décision** : Revoir la préparation avant soumission
- **Formule** : livrables renvoyés à leur première relecture ÷ livrables dont la première relecture est décidée.
- **Cible** : aucun seuil dans H7
- **Portée** : Flux : suit la période.
- **Limite** : pas de taux sous 30 décisions.

```dax
Renvois à la première relecture =
VAR vN = [Premières relectures décidées]
RETURN IF(vN >= 30, DIVIDE([Nombre de renvois en première relecture], vN))
```

### Phrases bloquantes à vérifier

- **Décision** : Quoi vérifier en premier
- **Formule** : phrases bloquantes, non acquittées, des livrables en relecture.
- **Cible** : 0 à l'approbation (règle du produit)
- **Portée** : Situation à la date des données : ne suit pas la période.

```dax
Phrases bloquantes à vérifier =
CALCULATE(SUM(Livrables[Phrases bloquantes]), KEEPFILTERS(Livrables[Code d'état] IN {"in_review"})) + 0
```

## Rapport

### Citations sans source après approbation

- **Décision** : Autoriser ou bloquer l'envoi au client
- **Formule** : citations de la version approuvée dont la source n'est pas dans le dossier.
- **Cible** : 0 (H7)
- **Portée** : Flux : suit la période.
- **Limite** : « non mesuré » si la version approuvée n'a pas de sections lisibles ; qu'une source existe ne prouve pas qu'elle soutient la phrase.

```dax
Citations sans source après approbation =
IF(MAX('Source des données'[Est une démonstration]) = 1, BLANK(), IF([Livrables mesurés] > 0, CALCULATE(SUM(Livrables[Citations sans source]), KEEPFILTERS(Livrables[Code d'état] IN {"approved"}), USERELATIONSHIP(Livrables[Clé d'approbation], Calendrier[Clé de date])) + 0))
```

### Citations sans source avant relecture

- **Décision** : Régler la recherche ou le modèle
- **Formule** : citations générées dont la source n'est pas dans le dossier ÷ citations générées.
- **Cible** : aucune : le critère H7 porte sur ce qui reste après approbation
- **Portée** : Flux : suit la période.

```dax
Citations sans source avant relecture =
IF(MAX('Source des données'[Est une démonstration]) = 1, BLANK(), IF([Citations générées] >= 30, DIVIDE([Nombre de citations sans source avant relecture], [Citations générées])))
```

### Phrases vérifiées

- **Décision** : Effort de relecture à prévoir
- **Formule** : phrases validées par le vérificateur ÷ phrases générées (TPV).
- **Cible** : aucune : H7 ne fixe pas de seuil sur le TPV
- **Portée** : Flux : suit la période.
- **Limite** : mesure l'ancrage dans les sources, pas la vérité.

```dax
Phrases vérifiées =
IF(MAX('Source des données'[Est une démonstration]) = 1, BLANK(), IF([Phrases générées] >= 30, DIVIDE([Nombre de phrases vérifiées], [Phrases générées])))
```

## Administration

### Alertes d'injection

- **Décision** : Examiner chaque passage signalé
- **Formule** : consignes cachées détectées dans les documents importés.
- **Cible** : examiner toutes les alertes
- **Portée** : Situation à la date des données : ne suit pas la période.
- **Limite** : une alerte est une détection, pas une attaque réussie.

```dax
Alertes d'injection =
SUM(Documents[Alertes]) + 0
```

### Documents signalés

- **Décision** : Revoir une source documentaire
- **Formule** : documents avec au moins une alerte d'injection ÷ documents importés.
- **Cible** : examiner toutes les alertes
- **Portée** : Situation à la date des données : ne suit pas la période.
- **Limite** : pas de taux sous 30 documents.

```dax
Documents signalés =
IF([Documents analysés] >= 30, DIVIDE([Nombre de documents signalés], [Documents analysés]))
```

## Recommandations

Règles déterministes, sans LLM. Les 3 plus prioritaires qui se déclenchent sur le périmètre filtré (client, type, consultant) s'affichent. Elles décrivent la situation à la date des données et ne suivent pas la période.

| Priorité | Code | Pour | Constat | Seuil | Action |
|---:|---|---|---|---|---|
| 1 | `citation_restante` | Responsable | Approuvés avec une citation sans source : n sur N livrables approuvés | au moins 1 citation sans source dans la version approuvée (H7 : 0) | Corriger puis faire réapprouver. |
| 2 | `relecture_en_retard` | Responsable | Relectures en retard : n sur N livrables en relecture | en relecture depuis plus de 48 h | Relire d'abord le plus ancien. |
| 3 | `renvoi_a_reprendre` | Consultant | Renvois à reprendre : n sur N livrables chez les consultants | renvoyé par un responsable et pas encore resoumis | Reprendre selon le motif du renvoi. |
| 4 | `bloquant_en_relecture` | Responsable | Soumis avec une phrase bloquante : n sur N livrables en relecture | au moins 1 phrase bloquante encore présente | Vérifier avant d'approuver. |
| 5 | `bloquant_avant_soumission` | Consultant | Brouillons avec une phrase bloquante : n sur N livrables chez les consultants | au moins 1 phrase bloquante encore présente | Corriger la source ou le chiffre. |
| 6 | `preuve_manquante` | Consultant | Sections refusées faute de preuve : n sur N livrables chez les consultants | au moins 1 section refusée dans la version courante | Ajouter le document manquant. |
| 7 | `brouillon_en_sommeil` | Consultant | Brouillons sans activité : n sur N livrables chez les consultants | aucune activité depuis plus de 5 jours | Soumettre ou signaler le blocage. |

## Alertes et tuiles

Les cartes portent des mesures numériques : dans Power BI Service, elles peuvent être épinglées et recevoir une alerte (voir [PUBLICATION.md](PUBLICATION.md)).

## Prédictions

### Charge de relecture des 2 prochaines semaines

- **Méthode** : moyenne des 8 dernières semaines glissantes × 2, renvois resoumis compris.
- **Intervalle** : 80 %, d'après les erreurs des prévisions rétrospectives. Leurs fenêtres se chevauchent : l'intervalle est indicatif.
- **Référence naïve** : répéter les 2 dernières semaines.
- **Publication** : au moins 30 soumissions et 10 prévisions vérifiables, et une erreur absolue moyenne inférieure à la référence. Sinon « historique insuffisant » ou « pas de prévision fiable ».

### Risque de renvoi d'un livrable en attente

- **Méthode** : taux de renvoi observé à la première relecture, selon la présence d'au moins une phrase bloquante, tous clients du cabinet.
- **Intervalle** : Wilson à 80 %, avec l'effectif du groupe.
- **Publication** : au moins 20 cas par groupe, 30 cas rétrospectifs et un score de Brier meilleur que le taux global.
- **Ordre de la file** : jours d'attente × (1 + risque de renvoi).

## Banc d'essai

Règle de [docs/08 §6](../docs/08-modele-rag-evaluation.md) : une configuration n'est retenue face à B que si l'intervalle à 95 % de l'écart de TPV (bootstrap apparié sur les sections) est au-dessus de 0 et qu'aucune métrique de sécurité ne se dégrade.
