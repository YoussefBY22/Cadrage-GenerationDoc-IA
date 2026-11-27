# 23 — Versions de l'application : ce que fait chaque version, opération par opération

> Lecteur : toi, un recruteur, un membre du jury. Ce document suit l'application **version par version** et
> dit, pour chaque opération (constats, recommandations, feuille de route, chat…), ce qu'elle faisait et ce
> qu'elle fait maintenant. Il complète [`20-comprendre-l-apprentissage.md`](20-comprendre-l-apprentissage.md),
> qui raconte les **entraînements** du modèle.

## 1. Comment les versions sont numérotées

- **V4** : le modèle **cadrage-4b-lora v4**, adopté le 24/11/2026 (Qwen3-4B affiné par QLoRA sur 341 exemples ;
  voir doc 20). C'est le « cerveau » utilisé par l'application.
- **V4.x** : la **même V4**, sans nouvel entraînement, améliorée par **le code autour du modèle** : des règles
  qui lisent le rapport (titres numérotés, échéances, numéros de paragraphe), la recherche dans les documents
  (RAG : on retrouve les bons passages avant de les donner au modèle), des garde-fous qui vérifient ce que le
  modèle écrit, et l'interface. Une version V4.x change ce que fait l'application **sans toucher aux poids du
  modèle** : c'est moins cher et plus sûr qu'un entraînement, et c'est vérifiable par des tests.
- **V5** : le troisième entraînement (Kaggle, 441 exemples, 43 min), **équivalent à V4** sur les tests, donc
  **non adopté** (doc 20 §4).
- Le **prochain entraînement** sera décidé à partir de la revue « consultant expert » de la V4.1 (section 4) :
  on n'entraîne que ce que le code ne peut pas corriger.

| Version | Date | Modèle | Ce qui a changé |
|---|---|---|---|
| V4.0 | 25/11/2026 | cadrage-4b-lora v4 | feuille de route par axes trouvés par le sens, TdR et cahier des charges sourcés, tableau de bord Power BI |
| V4.1 | 27/11/2026 | cadrage-4b-lora v4 (+ modèle de base pour reformuler) | lisibilité de l'interface, recommandations complètes, constats propres, feuille de route fondée sur les recommandations, visionneuse de preuves, tâches suivies en direct, recherche dynamique, assistant partout |

## 2. Ce que fait chaque version, opération par opération

| Opération | V4.0 | V4.1 |
|---|---|---|
| **Constats** | Le modèle **ne rédige pas** : il **copie** une phrase du rapport (pour que le vérificateur prouve qu'elle y est). Résultat : des phrases brutes, parfois sans sujet (« Cela étant, … »), et du bruit (phrases de méthode « Nous avons examiné si… », légendes de figure, cellules de tableau) : sur le rapport testé, ~30 sur 74 n'étaient pas des constats. | La phrase exacte reste la **preuve** (« Voir la phrase exacte du rapport »), et le texte affiché est **reformulé** en « Il a été constaté que… », en mots simples, sans changer les termes métier. Le bruit est **écarté par règles** (méthode, figure, tableau) ou par le modèle (contexte), avec la raison, et peut être rétabli. Garde-fous : un chiffre absent de la source fait rejeter la reformulation ; une phrase sans manque ni risque exprimé n'est pas classée « problème ». |
| **Doublons de constats** | Seules les phrases **identiques** étaient écartées : relancer l'extraction ajoutait des quasi-doublons (74 → 90). | Doublons trouvés **par le sens** (vecteurs bge-m3, similarité ≥ 0,93) et **fusionnés** : le constat garde toutes ses preuves ; « Défusionner » remet chacun tel quel. |
| **Nature des constats** | Pas de distinction. | **Problème**, **point positif** (« conforme aux règles ») ou **contexte** (écarté). Les points positifs ne justifient pas d'action dans la feuille de route. |
| **Recommandations** | Relevées **par une règle fixe** sur les titres « Recommandation n° X – … » : **le titre seulement**. Les sous-points a), b), c), l'échéance et les paragraphes cités étaient perdus. Fusionner deux recommandations affichait à tort « Manquant : n° 2 ». | **Contenu complet** repris du rapport, toujours par règles (copie exacte) : phrase d'introduction, **sous-points**, **échéance** (« D'ici à décembre 2023 »), **paragraphes cités** dans la conclusion (« (points 18 à 26) »). Fusionner ou supprimer est un choix du consultant, plus une alerte. Si le rapport n'a pas de titres numérotés, le contrôle le signale (« non détectées ») ; secours prévu : relevé par l'IA, chaque recommandation avec sa citation, marquée « proposée par l'IA ». |
| **Lien constat → recommandation** | Aucun. | Chaque constat est retrouvé dans le rapport, rattaché à **son paragraphe** (§ 30…) et donc à la **recommandation** qui cite ce paragraphe. Filtre « Recommandation n° 2 » dans les constats. |
| **Feuille de route** | Constats regroupés **par le sens** en ~6 axes nommés par le modèle, puis initiatives proposées par le modèle axe par axe (~22 min). Vagues **réparties par rang**, sans raison écrite. | S'il y a des recommandations : **une recommandation = un axe, un sous-point = une initiative**, constats liés comme justification. **Vague fixée par l'échéance** du rapport (dépassée : la gravité des constats départage), **raison écrite** sur chaque initiative (« Pourquoi cette vague : … »), lien « Voir dans le rapport ». Calcul **sans modèle** : quelques secondes. Sans recommandation : regroupement par le sens comme en V4.0. |
| **Suivi des tâches longues** | Le bouton devenait gris, rien ne s'affichait, impossible d'arrêter. | Bloc **en direct** : étape en cours (« Le modèle lit 8 passages de … p. 21–23 »), barre d'avancement, temps écoulé et **restant**, bouton **Arrêter** (entre deux appels au modèle), **historique** repliable ; la tâche continue si on quitte la page. Constats enregistrés au fil de l'eau. |
| **Lire un document** | Impossible depuis l'interface. | **Visionneuse** dans le navigateur, sans téléchargement : ouverte **sur la preuve, surlignée** ; jusqu'à 8 constats ou recommandations surlignés à la fois (une couleur chacun) ; bulle au survol ; choix « onglet déjà ouvert » ou « nouvel onglet ». |
| **Recherche** | Page vide, bouton « Rechercher », attente sans indicateur, but non expliqué. | **Dynamique** : mots exacts dès la frappe, puis **par le sens** après une pause, avec icône animée et temps écoulé ; une ligne explique à quoi elle sert ; chaque résultat montre document et page et s'ouvre dans la visionneuse. |
| **Chat** | Lié à la fiche de contexte, il ne servait qu'à proposer des valeurs de fiche ; il ne répondait pas quand le modèle travaillait déjà (extraction), sans rien afficher ; le message restait dans le champ. | **Assistant sur toutes les pages** (bulle). Réponses **instantanées, sans modèle** sur l'aide de la page et l'état du dossier ; sinon le modèle répond **en citant les passages** (document, page). Message affiché tout de suite, indicateur « le modèle prépare la réponse » avec temps écoulé, bouton **Arrêter**. Le chat de la fiche reste, pour proposer des valeurs de fiche. |
| **Modifier et supprimer** | Fiche projet illisible en modification ; pas de suppression de dossier, de document ni de livrable. | Fiche réparée ; suppression d'un **dossier** (avec tout son contenu), d'un **document** ou d'un **livrable**, après un message qui dit ce qui part. |
| **Comprendre l'écran** | Pages sans explication ; « [1] » pour la preuve ; livrables introuvables si on changeait de navigateur. | Une ligne d'explication sous chaque titre ; « Preuve 1 · document | p. 21 » ; barre de gauche dans l'ordre du travail ; livrables lus depuis le serveur. |
| **Bases existantes** | Une base créée par une version plus ancienne pouvait planter (colonne manquante). | Les colonnes nouvelles sont **ajoutées automatiquement** au démarrage, sans perte (migration 0006 pour PostgreSQL). |

## 3. Ce qui ne change pas

- Le modèle tourne **sur le poste**, aucune donnée ne sort.
- Chaque phrase d'un livrable cite sa source et le vérificateur la contrôle ; rien n'est validé sans un humain.
- Tout ce que fait le code autour du modèle est **réversible** : écarter, fusionner, reformuler se défont en un clic.

## 4. Revue « consultant expert » de la V4.1 et prochain entraînement

> Section remplie au test complet en utilisateur (nouveau dossier, de l'import du rapport au cahier des
> charges) : réponse par réponse, ce que le modèle a produit, ce qu'un consultant aurait écrit, l'écart, et
> si l'écart se corrige **par le code** (V4.x) ou demande **un entraînement** (V6).
