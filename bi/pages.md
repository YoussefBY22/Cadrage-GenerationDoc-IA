# Les pages du rapport

Quatre pages d'analyse et une page imprimable masquée, générées par [`pbip/rapport.py`](pbip/rapport.py).
Indicateurs, formules et règles d'action : [`KPI.md`](KPI.md). Qui voit quoi : [docs/14](../docs/14-acteurs-dashboard.md).

**Commun à toutes les pages** : barre latérale (navigation, bouton « Rapport imprimable ») et sept filtres
synchronisés :

- **Données** : réelles, démonstration, ou les deux (le défaut) ;
- **Période (au jour)** : deux dates et un curseur ;
- **Mois** ;
- **Projet** ;
- **Client** ;
- **Consultant** ;
- **Type de livrable**.

En-tête : le titre, le périmètre et la période (« Du 01/05/2026 au 30/11/2026 · 6 projets »), et à droite la nature
des données (« [DÉMO] 1 projet(s) réel(s) + 5 de démonstration »). Chaque graphique répète cette mention dans son
sous-titre. Pied : « Traitement local · données au … ».

| Page | Pour qui | Visuels | Décision |
|---|---|---|---|
| **Synthèse** | direction, responsable, consultant | 5 cartes (projets, livrables, taux d'erreur de l'IA hors refus voulus, temps moyen par appel, entraînements) · colonnes empilées « appels au modèle par mois » selon le résultat · anneau « livrables par état » (brouillon, en relecture, approuvé, renvoyé) · barres « activité par projet » · panneau **Que faire ensuite** (3 actions calculées par règles) | quoi faire en premier, et qui le fait |
| **Projet** | consultant, responsable | fiche (logo, client, secteur, demande, dates) · 4 cartes (documents, recommandations retenues sur annoncées, rapports en alerte, constats) · barres « recommandations par rapport d'audit » (validées, à valider, **manquantes en rouge**) · barres « constats par axe et gravité » · barres « feuille de route : initiatives par axe et vague » · barres 100 % « avancement des livrables » · barres « qualité par section » (libellé lisible ; info-bulle : à quoi sert la section, livrable, phrases, refus) | quel rapport revoir, quel axe charger, quelle section reprendre |
| **Qualité de l'IA** | consultant, profil technique | 4 cartes (phrases vérifiées, citations sans source, sections refusées, sorties invalides) · courbe « erreurs de l'IA par semaine » (le refus faute de preuve, voulu, à part en gris) · barres « erreurs par type » (info-bulle : ce que veut dire le type) · tableau « alertes : recommandations extraites ≠ annoncées » · colonnes « qualité par modèle » | où l'IA se trompe, et l'erreur vient-elle des documents ou du modèle |
| **Entraînement** | profil technique, jury | 4 cartes (entraînements, modèle adopté, erreur de validation retenue, exemples) · tableau des 3 entraînements (date, plateforme, exemples, durée, meilleure erreur, arrêt, décision) · courbe de validation par pas · barres « réussite par tâche : base contre modèles entraînés » | garder v4, refaire un entraînement, ou corriger par le code |
| **Rapport imprimable** (masquée, par bouton) | direction | 4 cartes · que faire ensuite · activité par mois · livrables par état · activité par projet · recommandations par rapport · limites | décider en réunion, papier en main |

Sur la page **Projet**, le filtre Projet est propre à la page (« Projet affiché ») et s'ouvre sur le projet réel ;
les autres filtres restent synchronisés.

Valeurs **réelles** : le projet « Recours aux consultants externes (RS 17/2022) » et les trois entraînements.
Valeurs **inventées** : les cinq projets « [DÉMO] », signalés partout.
