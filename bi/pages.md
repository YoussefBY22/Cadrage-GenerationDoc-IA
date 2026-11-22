# Les pages du rapport

Chaque page pose une question, et le titre de chaque visuel y répond par une phrase calculée selon les filtres.
Générées par [`pbip/rapport.py`](pbip/rapport.py) ; définitions dans [`KPI.md`](KPI.md).

Commun à toutes les pages : barre latérale (navigation, page active en jaune, segments Période, Client, Type de
livrable et Modèle synchronisés, bouton « Effacer les filtres ») et bandeau « Données de démonstration » affiché
seulement si les données le sont.

## Accueil : l'assistant tient-il ses promesses ?

| Visuel | Ce qu'il apprend |
|---|---|
| Verdict | nombre de critères H7 atteints sur 3, et lesquels |
| 5 cartes avec tendance mensuelle | temps gagné, acceptation sans retouche, citations inventées, phrases vérifiées, délai de validation |
| 4 tuiles | le fait marquant de chaque page et un lien pour l'ouvrir |

## Qualité et preuves : peut-on se fier à ce que l'assistant écrit ?

| Visuel | Ce qu'il apprend |
|---|---|
| 4 cartes | phrases vérifiées, citations inventées, chiffres retrouvés, refus faute de preuve |
| Cascade | combien de phrases sont perdues au contrôle, entre « à vérifier » et « rejetées » |
| Barres par motif et gravité | la première cause d'anomalie à corriger |
| Matrice section × configuration | les sections fragiles, avec mise en forme conditionnelle |

## Productivité et relecture : fait-il gagner du temps au consultant ?

| Visuel | Ce qu'il apprend |
|---|---|
| 5 cartes | temps gagné, gain par livrable, acceptation sans retouche, délai, renvois |
| Entonnoir | demandées → rédigées → approuvées → sans retouche : l'étape où l'on perd |
| Colonnes par ampleur de retouche | retouches légères ou réécritures |
| Barres par section | les gabarits à améliorer en premier |

## Comparaison des modèles : quelle configuration faut-il retenir ?

| Visuel | Ce qu'il apprend |
|---|---|
| Petits multiples | la meilleure configuration sur quatre critères de qualité |
| Bilan | écart à la référence B, citations inventées, refus, temps de réponse, taille d'échantillon |
| Nuage | l'arbitrage entre qualité et vitesse |

## Sécurité et usage : est-il utilisé, et sans danger ?

| Visuel | Ce qu'il apprend |
|---|---|
| 4 cartes | alertes, documents signalés, missions actives, livrables approuvés |
| Barres par mission | où enquêter |
| Barres par format | quels types de fichiers surveiller |
| Petits multiples par client | qui utilise l'outil, et si l'usage dure |
