# 14 — Acteurs du tableau de bord

> Qui voit quoi, pour décider quoi. Indicateurs : [`bi/KPI.md`](../bi/KPI.md). Ouverture : [`bi/README.md`](../bi/README.md).
> Mise en ligne (préparée, non faite) : [`bi/PUBLICATION.md`](../bi/PUBLICATION.md).
> Les chiffres du jeu de démonstration sont **inventés**.

## 1. À qui sert le rapport

Deux acteurs d'abord, ceux de l'application ([01 §4](01-cahier-des-charges.md), H6) : le **consultant** rédige avec
l'assistant, le **responsable** valide. Deux lecteurs secondaires : le **profil technique** et la **direction**.

| Acteur | Ses questions | Page | KPI (4 au plus) | Décision | Ce qu'il ne doit pas voir |
|---|---|---|---|---|---|
| **Consultant** | Que reprendre ? Pourquoi m'a-t-on renvoyé ? Quoi corriger avant de soumettre ? | Production | livrables à traiter · phrases bloquantes · sections sans retouche · temps gagné (hypothèse) | quel livrable commencer, quoi corriger, garder ou retravailler le premier jet | les livrables, clients et prévisions des autres consultants |
| **Responsable** | Que valider d'abord ? Qu'est-ce qui attend trop ? Qui est chargé ? | Validation | livrables à valider · délai · renvois en 1re relecture · phrases bloquantes à vérifier | ordre de relecture, répartition, renvoi avec motif | les dossiers dont il n'est pas le responsable ; un classement des personnes |
| Les deux, et la **direction du cabinet** | Où en est-on ? Que faire en premier ? Quelle charge arrive ? | Synthèse | livrables à valider · à traiter · citations sans source après approbation · délai | priorités, envoi au client, renfort de relecture | le texte des livrables et des documents (absent de l'entrepôt) |
| **Profil technique** | Le modèle tient-il ? Faut-il en changer ? Des documents sont-ils piégés ? | Administration | phrases vérifiées · sans source avant relecture · alertes · documents signalés | régler la recherche, garder B, examiner un document | le texte des documents (absent de l'entrepôt) |
| **Direction d'un client** | Où en sont mes livrables ? | **aucune** : un fichier | ceux du rapport, filtrés sur son entreprise | valider un planning | le tableau de bord multi-client, les autres clients, les noms de personnes, le risque estimé sur l'historique des autres |

La page **Rapport** est masquée et s'ouvre par le bouton « Rapport imprimable » : constat, recommandations, critères
H7, indicateurs, prédiction, limites, date. Elle suit les quatre filtres.

### Un rôle choisi à l'écran n'est pas une sécurité

- Dans Power BI Desktop, choisir une page ou son nom dans un segment est un **filtre de confort**. Qui a le fichier
  a toutes les données.
- Les rôles RLS du modèle (`Consultant`, `Responsable`, `Administration`) ne s'appliquent dans le Service qu'aux
  **Lecteurs** de l'espace de travail, pas aux administrateurs, membres et contributeurs.
- La RLS filtre des **lignes**, elle ne cache pas une page.
- Pour la direction d'un client, **ne jamais partager le rapport**. Produire un fichier :

  ```powershell
  python -m app.dw.report --audience client --client "Nom du client" --out client.pdf
  ```

  La commande refuse ce public sans client, et ce document ne contient ni personne, ni autre client, ni risque.
  Exemple : [`rapport-client-demo.pdf`](../bi/exemples/rapport-client-demo.pdf).

## 2. Ce que disent les pages

- **Titre** nominal, **sous-titre** avec périmètre, mesure et période, **constat** dans sa propre zone.
- **Période** : elle porte sur les flux (générations, soumissions, approbations). La file, les recommandations et la
  prédiction décrivent la situation à la date des données.
- **Effectif** : un taux va avec son n et disparaît sous 30 cas. Un critère non mesuré n'a pas de verdict. « Zéro
  citation sans source » ne vaut « atteint » qu'à partir de 30 livrables mesurés, alors qu'une seule suffit pour
  « non atteint ».

## 3. Recommandations

Sept règles déterministes, sans LLM : constat chiffré, seuil, acteur, action. Elles sont définies une seule fois dans
[`pilotage.py`](../backend/app/dw/pilotage.py). L'ETL les évalue par livrable (`fact_action`), puis Power BI et la
commande de rapport ne font que compter dans le périmètre filtré. Table complète :
[`bi/KPI.md`](../bi/KPI.md#recommandations).

## 4. Prédiction

| | Charge de relecture | Risque de renvoi |
|---|---|---|
| Question | combien de soumissions dans les 2 prochaines semaines ? | ce livrable en attente sera-t-il renvoyé ? |
| Méthode | moyenne des 8 dernières semaines × 2 | taux observé selon la présence d'une phrase bloquante |
| Intervalle | 80 %, erreurs des prévisions passées | 80 %, Wilson, avec n |
| Référence naïve | répéter les 2 dernières semaines | taux de renvoi global |
| Publiée si | ≥ 30 soumissions, ≥ 10 prévisions testées, erreur plus faible | ≥ 20 cas par groupe, ≥ 30 testés, Brier meilleur |
| Sinon | « historique insuffisant » ou « pas de prévision fiable » | « non publié » |
| Sur la démo (simulation) | 10 [8 ; 12], n = 199 ; erreur 1,6 contre 2,3 | 6 % (n = 104) ou 41 % (n = 61) ; Brier 0,126 contre 0,151 |

La série affichée est régulière, au pas de 14 jours, celui de la prévision. Il n'y a pas de visuel d'IA : le volume
ne le justifie pas, et la méthode doit pouvoir s'expliquer en une phrase. Les fenêtres des tests se chevauchent, donc
l'intervalle est indicatif. Ces résultats viennent de données inventées : ils prouvent le mécanisme, pas son pouvoir
prédictif.

## 5. Audit du 22/11/2026 : avant, après

| # | Avant | Après | Preuve |
|---|---|---|---|
| 1 | A/B/C/D de la démo contredisait [08 §6](08-modele-rag-evaluation.md) (LoRA en D, modèles 7, 8 et 14 B inventés) | banc séparé : A sans recherche, C = B + LoRA, D = autre taille ; production sans étiquette | `test_configurations_follow_the_protocol` |
| 2 | 13 fichiers Excel, format refusé à l'import | uniquement les formats de `app/ingest` | `test_only_formats_the_ingestion_accepts` |
| 3 | « Excel le plus signalé », faux en taux | taux, n et nombre par format, titre neutre | page Administration |
| 4 | novembre à 7 générations, tendances artefacts | 38 semaines régulières, n affiché, aucun taux sous 30 | `pilotage.MIN_SAMPLE` |
| 5 | citations détectées présentées comme le critère H7 | deux mesures : avant relecture, et **après approbation** (version approuvée) | `test_snapshot_measures_what_remains_after_approval` |
| 6 | « plancher 50 % » avec coche verte, temps gagné présenté comme acquis | coche retirée, temps « ≈ », « hypothèse, non mesuré » | cartes, rapport |
| 7 | « aucune donnée client », segments « All » | « Traitement local · confidentiel » hors démo, vraie valeur « Tous » | `modele.py` |
| 8 | « retenir C » sans intervalle ni règle | IC 95 % et règle de 08 §6, même calcul que le banc d'évaluation : C non concluant | `test_bench_decision_is_the_one_of_the_eval_harness` |
| 9 | pages qui jugent le produit, ni auteur ni relecteur | pages par acteur, KPI liés à une décision, auteur et responsable exposés | `v_deliverable` |
| 10 | 16 livrables approuvés sur 16, rien à piloter | brouillons, file, renvois avec motif, transitions conformes au circuit | `test_there_is_work_to_steer` |

Trouvé en chemin :

- `services/generation.py` écrit `config_label = "default"`, trop long pour `dim_model.config_label` (1 caractère) :
  l'ETL aurait échoué sur PostgreSQL. Corrigé dans l'ETL, avec un test.
- Le rapport Python arrondissait au pair (2,25 → 2,2) et Power BI vers le haut (2,3). Aligné sur Power BI.

Le premier jet de ce lot avait sept pages et des titres en forme de question. Il a été ramené à quatre pages visibles
et des titres nominaux avant livraison.

## 6. Règles de conception : source, application

Sources lues le 22/11/2026. **Non vérifié** : la source primaire n'a pas pu être lue, la règle est donc un choix.

| Règle | Source | Statut | Application |
|---|---|---|---|
| Un rapport a des pages et des filtres ; un tableau de bord est une page de tuiles du Service, sans segment, avec alertes | [Learn, dashboards](https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards) | lu | ceci est un rapport ; tuiles à épingler dans `PUBLICATION.md` |
| Ne pas mêler des sujets ou objectifs opposés sur une page ; l'important en haut à gauche ; répétition | [Learn, mise en page](https://learn.microsoft.com/en-us/training/modules/power-bi-effective-reports/2-design-layout) | lu | une page par acteur, même grille |
| Retirer le superflu ; cartes pour les nombres clés, avec contexte ; échelles et couleurs constantes | [Learn, conseils de conception](https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards-design-tips) | lu | 4 cartes au plus, n et décision sur chacune |
| Ne garder que les visuels nécessaires | [Learn, optimisation](https://learn.microsoft.com/en-us/power-bi/guidance/power-bi-optimization) | lu ; aucun maximum chiffré n'y figure | « 4 pages, 4 KPI » est un choix du projet |
| Noms de pages courts et nominaux | exemples officiels [Competitive Marketing](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-competitive-marketing-analysis) (« Executive Overview »), [Corporate Spend](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-corporate-spend) (« IT Spend Trend »), [Store Sales](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-store-sales) (« Store Sales Overview ») | lu : aucun titre interrogatif | Synthèse, Production, Validation, Administration |
| Texte alternatif (250 caractères au plus), décor hors tabulation, titres de même taille, pas de jargon | [Learn, accessibilité](https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-accessibility-creating-reports) | lu | texte alternatif sur les objets porteurs, `tabOrder` négatif pour le décor, titres en 13 |
| Contraste d'au moins 4,5:1 ; pas d'information par la seule couleur ; pas de vert contre rouge | même page | lu, contrastes calculés | texte gris `#5F5F6B` (5,8:1 sur le fond), formes de points, plus de vert |
| Ne pas mettre l'essentiel dans une info-bulle | même page | lu | n et décision écrits sur la carte |
| Prévision native : courbe avec données de temps | [Learn, volet Analytique](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-analytics-pane) | lu ; « une seule série » n'y figure pas | prévision calculée par l'ETL pour porter le test rétrospectif |
| RLS limitée aux Lecteurs ; rôles additifs ; sans rôle, aucune ligne | [Learn, RLS](https://learn.microsoft.com/en-us/fabric/security/service-admin-row-level-security), [guide](https://learn.microsoft.com/en-us/power-bi/guidance/rls-guidance) | lu | trois rôles, un par personne |
| L'export PDF de Desktop exclut les pages masquées | [Learn, export PDF](https://learn.microsoft.com/en-us/power-bi/collaborate-share/end-user-pdf) | lu | le fichier officiel vient de `app.dw.report` |
| Alertes sur cartes, KPI et jauges numériques | [Learn, alertes](https://learn.microsoft.com/en-us/power-bi/create-reports/service-set-data-alerts) | lu | cartes en mesures numériques |
| ISO 24896 « Notation for business reporting » publiée en juin 2026, IBCS 2.0 aligné dessus | [IBCS](https://www.ibcs.com/iso-24896/) | lu chez IBCS seulement ; iso.org a refusé la lecture | — |
| Titre « qui, quoi, quand » ; message séparé du titre | IBCS 2.0 | **non vérifié** : le texte des règles n'est pas publié sur les pages lisibles | sous-titre périmètre, mesure, période ; zone Constat |
| Contenu de la norme ISO 24896 (notations, échelles, surlignage) | ISO | **non vérifié** : norme payante, non lue | aucune conformité revendiquée |
