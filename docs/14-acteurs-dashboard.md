# 14 — Acteurs du tableau de bord

> Qui voit quoi, pour décider quoi. Pages : [`bi/pages.md`](../bi/pages.md). Indicateurs et règles d'action :
> [`bi/KPI.md`](../bi/KPI.md). Ouverture : [`bi/README.md`](../bi/README.md). Mise en ligne (préparée, non faite) :
> [`bi/PUBLICATION.md`](../bi/PUBLICATION.md).

## 1. Pourquoi Power BI, et pas des statistiques dans l'application

L'application montre déjà, dossier par dossier, ce qu'il faut corriger. Le rapport Power BI sert à ce qu'elle ne fait
pas :

- **analyser dans le temps et entre projets** : courbes par jour et par mois, comparaison de projets, de modèles,
  d'entraînements ;
- **explorer** : filtres croisés (cliquer une barre filtre la page), sept filtres synchronisés, info-bulles qui
  expliquent chaque section et chaque type d'erreur ;
- **rendre compte** : une page imprimable pour la direction ;
- **décider** : un panneau « Que faire ensuite » qui donne trois actions calculées par des règles explicites.

La refonte du 25/11/2026 part d'un constat de l'utilisateur sur la version précédente : que des phrases et des
tableaux de texte, aucune courbe, des colonnes tronquées, des clés techniques (`chg_parties`) et des titres flous.
Chaque page porte désormais au moins un vrai graphique, aucune clé technique ne s'affiche, et chaque section a son
libellé et son rôle (lus dans les gabarits).

## 2. À qui sert chaque page

| Acteur | Ses questions | Page | Décision |
|---|---|---|---|
| **Direction du cabinet** | Combien de projets, à quel rythme, avec quelle qualité ? Que faire en premier ? | Synthèse, Rapport imprimable | priorités, renfort, envoi au client |
| **Consultant** | Mes rapports ont-ils été bien lus ? Quelles recommandations manquent ? Quelle section reprendre ? | Projet, Qualité de l'IA | compléter les recommandations, revoir les sources, compléter les documents |
| **Responsable** | Qu'est-ce qui attend ma validation ? Qu'ai-je renvoyé ? | Synthèse (livrables par état), Projet (avancement) | ordre de relecture |
| **Profil technique, jury** | Où le modèle se trompe-t-il ? L'entraînement a-t-il servi ? Quel modèle garder ? | Qualité de l'IA, Entraînement | garder v4, refaire un entraînement, corriger par le code |
| **Direction d'un client** | Où en sont mes livrables ? | **aucune** | ce rapport est interne au cabinet, même filtré |

### Un rôle choisi à l'écran n'est pas une sécurité

- Dans Power BI Desktop, un filtre est un confort : qui a le fichier a toutes les données.
- Les rôles RLS du modèle (`Consultant` : projets où il a rédigé ou généré ; `Responsable` : projets où il relit ;
  `Administration`) ne s'appliquent dans le Service qu'aux **Lecteurs** de l'espace de travail.
- Ne jamais transmettre le rapport ni son PDF à un client.

## 3. Démonstration et données réelles

- Valeurs **réelles** : le projet « Recours aux consultants externes (RS 17/2022) » (rapport spécial de la Cour des
  comptes européenne, 74 constats, feuilles de route, TdR, CdC) et les trois entraînements (registre
  `training/registre/`).
- Valeurs **inventées** : cinq projets « [DÉMO] », pour montrer les courbes et la comparaison entre projets. Leur
  client porte « (démo) », leur nom « [DÉMO] », et tout visuel qui les inclut le dit dans son sous-titre. Le filtre
  **Données** permet de n'afficher que le réel.
- Aucune mesure de qualité inventée n'est présentée comme réelle : sans filtre, le sous-titre l'annonce ; avec le
  filtre « Réelles », il ne reste que le projet réel.

## 4. Que faire ensuite : règles explicites

Sept règles, sans modèle de langue, évaluées sur le périmètre filtré ; les trois premières qui se déclenchent
s'affichent. Exemples : un rapport d'audit annonce les recommandations 1 à 4 mais le n° 3 manque → « Contrôler 1
rapport d'audit » ; plus de 20 % de sections refusées → « Compléter les documents », avec la section la plus
refusée. Table complète : [`bi/KPI.md`](../bi/KPI.md#que-faire-ensuite--règles-daction).

## 5. Détecter vite une erreur de l'IA

Le cas typique : le rapport numérote « Recommandation n° 1 à 4 », mais seulement 3 sont retenues. L'application
relève les titres numérotés par des règles, le consultant valide, fusionne, ajoute ou supprime, et le contrôle de
cohérence compare à ce que le rapport annonce (trous, doublons). Un rapport sans aucun titre numéroté n'est jamais un
« 0 » silencieux : il est marqué « recommandations non détectées : à saisir ou valider par le consultant » et compté
dans les alertes. Le tableau de bord affiche la version corrigée.

Étape suivante, non faite : une extraction par le modèle, en secours, pour les rapports qui ne numérotent pas leurs
recommandations.

## 6. Règles de conception : source, application

Sources lues le 22/11/2026. **Non vérifié** : la source primaire n'a pas pu être lue, la règle est donc un choix.

| Règle | Source | Statut | Application |
|---|---|---|---|
| Un rapport a des pages et des filtres ; un tableau de bord est une page de tuiles du Service, sans segment, avec alertes | [Learn, dashboards](https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards) | lu | ceci est un rapport ; tuiles à épingler dans `PUBLICATION.md` |
| Ne pas mêler des sujets ou objectifs opposés sur une page ; l'important en haut à gauche ; répétition | [Learn, mise en page](https://learn.microsoft.com/en-us/training/modules/power-bi-effective-reports/2-design-layout) | lu | une page par question (synthèse, projet, qualité, entraînement), même grille |
| Retirer le superflu ; cartes pour les nombres clés, avec contexte ; échelles et couleurs constantes | [Learn, conseils de conception](https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards-design-tips) | lu | 4 ou 5 cartes, effectif sous chaque taux |
| Ne garder que les visuels nécessaires | [Learn, optimisation](https://learn.microsoft.com/en-us/power-bi/guidance/power-bi-optimization) | lu ; aucun maximum chiffré n'y figure | « 4 pages, 5 cartes au plus » est un choix du projet |
| Noms de pages courts et nominaux | exemples officiels [Competitive Marketing](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-competitive-marketing-analysis) (« Executive Overview »), [Corporate Spend](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-corporate-spend) (« IT Spend Trend »), [Store Sales](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-store-sales) (« Store Sales Overview ») | lu : aucun titre interrogatif | Synthèse, Projet, Qualité de l'IA, Entraînement |
| Texte alternatif (250 caractères au plus), décor hors tabulation, titres de même taille, pas de jargon | [Learn, accessibilité](https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-accessibility-creating-reports) | lu | texte alternatif sur les objets porteurs, `tabOrder` négatif pour le décor, titres en 13 |
| Contraste d'au moins 4,5:1 ; pas d'information par la seule couleur ; pas de vert contre rouge | même page | lu, contrastes calculés | texte gris `#5F5F6B` (5,8:1 sur le fond), rouge réservé à ce qui demande une action et toujours légendé, pas de vert |
| Ne pas mettre l'essentiel dans une info-bulle | même page | lu | effectif écrit sur la carte ; l'info-bulle n'ajoute que des explications (rôle d'une section, sens d'un type d'erreur) |
| Prévision native : courbe avec données de temps | [Learn, volet Analytique](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-analytics-pane) | lu ; « une seule série » n'y figure pas | pas de prévision affichée dans cette version |
| RLS limitée aux Lecteurs ; rôles additifs ; sans rôle, aucune ligne | [Learn, RLS](https://learn.microsoft.com/en-us/fabric/security/service-admin-row-level-security), [guide](https://learn.microsoft.com/en-us/power-bi/guidance/rls-guidance) | lu | trois rôles, un par personne |
| L'export PDF de Desktop exclut les pages masquées | [Learn, export PDF](https://learn.microsoft.com/en-us/power-bi/collaborate-share/end-user-pdf) | lu | le fichier officiel vient de `app.dw.report` |
| Alertes sur cartes, KPI et jauges numériques | [Learn, alertes](https://learn.microsoft.com/en-us/power-bi/create-reports/service-set-data-alerts) | lu | cartes en mesures numériques |
| ISO 24896 « Notation for business reporting » publiée en juin 2026, IBCS 2.0 aligné dessus | [IBCS](https://www.ibcs.com/iso-24896/) | lu chez IBCS seulement ; iso.org a refusé la lecture | — |
| Titre « qui, quoi, quand » ; message séparé du titre | IBCS 2.0 | **non vérifié** : le texte des règles n'est pas publié sur les pages lisibles | sous-titre périmètre et période ; message dans « Que faire ensuite » |
| Contenu de la norme ISO 24896 (notations, échelles, surlignage) | ISO | **non vérifié** : norme payante, non lue | aucune conformité revendiquée |
