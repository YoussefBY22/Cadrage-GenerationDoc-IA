# Indicateurs du tableau de bord Power BI

> Fichier généré par `python bi/pbip/build_pbip.py` depuis [`pbip/indicateurs.py`](pbip/indicateurs.py).
> La même définition figure dans la description de chaque mesure (info-bulle du volet Données)
> et dans l'icône d'information des cartes du rapport.

## Critères de réussite (hypothèse H7)

Source : [cahier des charges](../docs/01-cahier-des-charges.md), §13. H7 est une hypothèse de travail, à valider avec l'entreprise.

| Critère H7 | Indicateur du rapport | Cible |
|---|---|---|
| 0 citation inventée | Citations inventées | 0 |
| Phrases réutilisables telles quelles | Sections acceptées sans retouche (approximation plus sévère) | ≥ 50 % |
| Temps gagné sur la rédaction | Temps gagné (estimation) | ≥ 30 % |

Le verdict de la page d'accueil porte sur ces trois critères. Les autres indicateurs expliquent le résultat et n'ont pas de seuil, sauf le plancher des phrases vérifiées, déduit de H7. Le palier de 80 % qui colore la matrice est un repère de lecture, pas une cible.

## 1. Qualité et preuves

### Phrases vérifiées

- **Formule** : phrases validées par le vérificateur ÷ phrases des sections générées (TPV, taux de phrases vérifiées).
- **Pourquoi** : c'est la promesse du produit : chaque phrase s'appuie sur une preuve du dossier.
- **Cible** : au moins 50 %. Ce plancher est déduit de H7 : une phrase non vérifiée n'est pas réutilisable telle quelle.
- **Limite** : mesure l'ancrage dans les sources, pas la vérité du contenu.

```dax
Phrases vérifiées =
DIVIDE([Nombre de phrases vérifiées], [Phrases générées])
```

### Citations inventées

- **Formule** : citations produites − citations dont la source existe dans le dossier.
- **Pourquoi** : une source inexistante ou prise dans un autre dossier ruine la confiance et peut fuiter entre clients.
- **Cible** : 0 (H7).
- **Limite** : compte ce que le modèle a produit et que le vérificateur a signalé, pas ce qui reste après relecture.

```dax
Citations inventées =
VAR vTotal = SUM('Générations'[Citations produites])
RETURN IF(NOT ISBLANK(vTotal), vTotal - SUM('Générations'[Citations valides en nombre]))
```

### Chiffres retrouvés dans la source

- **Formule** : chiffres cités retrouvés dans le passage source ÷ chiffres cités.
- **Pourquoi** : un montant, un délai ou un taux faux est l'erreur la plus coûteuse dans un livrable de conseil.
- **Cible** : Aucun seuil dans H7 : indicateur de suivi.
- **Limite** : vide si aucun chiffre n'est cité (kpi.py renvoie 1 dans ce cas).

```dax
Chiffres retrouvés dans la source =
DIVIDE(SUM('Générations'[Chiffres retrouvés]), SUM('Générations'[Chiffres cités]))
```

### Sections refusées faute de preuve

- **Formule** : générations de sections refusées ÷ générations de sections (constats exclus).
- **Pourquoi** : un refus vaut mieux qu'une invention ; un taux élevé révèle des dossiers trop pauvres ou une recherche mal réglée.
- **Cible** : Aucun seuil dans H7 : indicateur de suivi.
- **Limite** : kpi.py rapporte les refus à toutes les générations, constats compris.

```dax
Sections refusées faute de preuve =
DIVIDE([Nombre de sections refusées], [Générations de sections])
```

## 2. Productivité et relecture

### Temps gagné

- **Formule** : minutes gagnées sur les sections rédigées ÷ minutes d'une rédaction manuelle de toutes les sections approuvées.
- **Pourquoi** : c'est le retour sur investissement attendu par le cabinet.
- **Cible** : au moins 30 % (H7).
- **Limite** : estimation : 30 min par section manuelle (à valider), gain proportionnel au texte conservé, relecture non déduite. Une section refusée ne fait rien gagner.

```dax
Temps gagné =
DIVIDE(
    CALCULATE(SUM('Sections approuvées'[Minutes gagnées]), KEEPFILTERS('Sections approuvées'[Refusée] = 0)),
    SUM('Sections approuvées'[Minutes de référence]))
```

### Temps gagné par livrable

- **Formule** : heures gagnées ÷ livrables approuvés.
- **Pourquoi** : traduit le pourcentage en temps de consultant rendu à l'analyse.
- **Cible** : aucun seuil en heures dans H7, qui raisonne en pourcentage (voir Temps gagné).
- **Limite** : même estimation que Temps gagné.

```dax
Temps gagné par livrable =
DIVIDE([Heures gagnées], [Livrables approuvés])
```

### Sections acceptées sans retouche

- **Formule** : sections approuvées mot pour mot ÷ sections rédigées puis approuvées (refus exclus).
- **Pourquoi** : mesure l'adoption réelle : le consultant garde le texte au lieu de le refaire.
- **Cible** : au moins 50 % (H7, « réutilisables telles quelles »).
- **Limite** : H7 raisonne par phrase et l'entrepôt par section : une seule retouche disqualifie la section, la mesure est donc plus sévère que H7.

```dax
Sections acceptées sans retouche =
DIVIDE([Nombre de sections sans retouche], [Sections rédigées puis approuvées])
```

### Délai de validation

- **Formule** : médiane des heures entre la première soumission et l'approbation, par livrable.
- **Pourquoi** : le temps gagné à la rédaction est perdu si le livrable attend en relecture.
- **Cible** : Aucun seuil dans H7 : indicateur de suivi.
- **Limite** : heures calendaires ; non filtré par modèle, car un livrable peut en mélanger plusieurs.

```dax
Délai de validation =
MEDIAN(Relectures[Délai en heures])
```

### Renvois en correction

- **Formule** : renvois par le relecteur ÷ soumissions en relecture.
- **Pourquoi** : signale des brouillons qui arrivent trop tôt ou trop fragiles chez le manager.
- **Cible** : Aucun seuil dans H7 : indicateur de suivi.
- **Limite** : non filtré par modèle.

```dax
Renvois en correction =
DIVIDE(SUM(Relectures[Renvois]), SUM(Relectures[Soumissions]))
```

## 3. Comparaison des modèles

### Écart à la référence B

- **Formule** : (phrases vérifiées de la configuration − celles de la référence B) × 100, en points.
- **Pourquoi** : un modèle plus lourd ou affiné ne se justifie que s'il fait mieux que la référence.
- **Cible** : supérieur à 0 pour justifier un changement ; H7 ne fixe pas de seuil.
- **Limite** : échantillons de tailles différentes : lire avec le nombre de générations.

```dax
Écart à la référence B =
VAR vTaux = [Phrases vérifiées]
VAR vReference = CALCULATE([Phrases vérifiées], REMOVEFILTERS(Configurations), Configurations[Configuration] = "B")
RETURN IF(NOT ISBLANK(vTaux) && NOT ISBLANK(vReference), (vTaux - vReference) * 100)
```

### Temps de réponse p95

- **Formule** : 95e centile de la durée d'un appel de rédaction de section, en secondes.
- **Pourquoi** : au-delà de quelques dizaines de secondes, le consultant cesse d'utiliser l'outil ; cette mesure arbitre qualité contre vitesse.
- **Cible** : Aucun seuil dans H7 : indicateur de suivi.
- **Limite** : appels de section seulement (kpi.py prend tous les appels) ; la latence d'une tentative répétée est répartie à parts égales.

```dax
Temps de réponse p95 =
CALCULATE(
    PERCENTILEX.INC('Appels au modèle', 'Appels au modèle'[Latence en ms], 0.95) / 1000,
    KEEPFILTERS('Appels au modèle'[Nature] = "section"))
```

## 4. Sécurité et usage

### Alertes d'injection

- **Formule** : somme des consignes cachées détectées dans les documents importés.
- **Pourquoi** : un document piégé peut détourner le modèle ; chaque alerte demande un examen humain.
- **Cible** : aucun seuil dans H7 ; examiner 100 % des alertes.
- **Limite** : compte les détections, pas les attaques réussies ; non filtré par modèle ni par type de livrable.

```dax
Alertes d'injection =
IF([Documents analysés] > 0, SUM(Documents[Alertes]) + 0)
```

### Documents signalés

- **Formule** : documents avec au moins une alerte ÷ documents importés.
- **Pourquoi** : situe le risque : incident isolé ou source documentaire à revoir.
- **Cible** : Aucun seuil dans H7 : indicateur de suivi.
- **Limite** : un document est daté de la première génération de sa mission.

```dax
Documents signalés =
DIVIDE([Nombre de documents signalés] + 0, [Documents analysés])
```

### Livrables approuvés

- **Formule** : nombre de livrables distincts approuvés par un manager.
- **Pourquoi** : c'est l'usage qui compte : un brouillon non approuvé ne crée pas de valeur.
- **Cible** : Aucun seuil dans H7 : indicateur de suivi.

```dax
Livrables approuvés =
DISTINCTCOUNT('Sections approuvées'[Identifiant du livrable])
```

## Écarts volontaires avec `backend/app/dw/kpi.py`

- **Sections refusées** : l'entrepôt les enregistre « inchangées », avec 30 minutes gagnées chacune (0 mot généré, 0 mot final). Le rapport les exclut des sections sans retouche et du temps gagné. `kpi.unchanged_rate` et `kpi.minutes_saved` les comptent encore et donnent donc des valeurs plus flatteuses.
- **Taux de refus** : rapporté aux générations de sections, constats exclus.
- **Temps de réponse p95** : calculé sur les appels de section, pour comparer des tâches identiques.
- **Chiffres retrouvés** : vide, et non 100 %, quand aucun chiffre n'est cité.

Le taux de phrases vérifiées, les citations valides, le délai de validation, les renvois en correction et les alertes d'injection suivent les mêmes formules que `kpi.py`.
