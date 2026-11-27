# 20 — Comprendre l'apprentissage du modèle (les trois entraînements, expliqués simplement)

> Lecteur : toi, ton encadrant, un jury. Aucun prérequis. Chaque mot technique est expliqué la première fois.
> Tous les chiffres viennent des journaux d'entraînement et des tests réels (Colab, Kaggle, PC). Détails techniques :
> [`19-entrainement-et-tests-reels.md`](19-entrainement-et-tests-reels.md).

## 1. Ce qu'on a fait, en une phrase

On a pris un modèle de langue existant (**Qwen3-4B**), on lui a montré quelques centaines d'exemples de « bonnes
réponses » tirés de rapports publics, et on a ajusté un **petit calque** de réglages pour qu'il réponde comme notre
application l'exige : citer ses sources, refuser quand il n'y a pas de preuve, lire la position d'une institution,
extraire des constats, ranger des constats en axes.

## 2. Ce que c'est, et ce que ce n'est pas

| C'est | Ce n'est pas |
|---|---|
| Un **ajustement du comportement** : le format JSON, la façon de citer, le refus, le vocabulaire de l'audit | Un ajout de **connaissances** : le modèle n'apprend aucun fait sur un client ; les faits viennent toujours des documents déposés |
| Un **petit calque** (une LoRA, ~1 % de la taille du modèle) posé sur le modèle d'origine, qu'on peut retirer | Un nouveau modèle construit de zéro (impossible avec nos moyens, et inutile) |
| Un entraînement **ponctuel, volontaire et vérifié** (on mesure avant de l'adopter) | Un apprentissage **continu** : le modèle n'apprend pas tout seul en l'utilisant ; les corrections du consultant servent d'abord de contexte, puis, après validation, d'exemples pour un prochain entraînement |
| Fait sur des **documents publics** (Cour des comptes européenne, licence CC BY 4.0) | Fait sur des documents de client (jamais sans accord écrit) |

## 3. Les mots, expliqués

| Mot | Explication simple |
|---|---|
| **Modèle de langue** | Un programme qui prédit le mot suivant. À force, il sait écrire, résumer, classer. Le nôtre a 4 milliards de « réglages » internes (paramètres). |
| **LoRA / QLoRA** | Plutôt que modifier les 4 milliards de réglages, on ajoute un petit calque de réglages qu'on entraîne seul. QLoRA : la même chose avec le modèle compressé (4 bits) pour tenir sur un GPU gratuit. |
| **Exemple d'entraînement** | Une question (consigne + passages) et la réponse attendue. Ici, les réponses sont des phrases **recopiées** des rapports publics, jamais inventées. |
| **Train / validation / test** | Trois tas séparés **par rapport** : on apprend sur « train » ; on surveille sur « validation » ; on note à la fin sur « test », que le modèle n'a jamais vu. Un rapport n'est jamais dans deux tas à la fois (sinon le modèle « connaîtrait les réponses »). |
| **Pas** | Le modèle lit un petit lot d'exemples (ici 4), calcule son erreur, et corrige un peu ses réglages. |
| **Époque** | Le modèle a vu une fois tous les exemples d'entraînement. 341 exemples / 4 par pas ≈ 85 pas ; 441 / 4 ≈ 111 pas. |
| **Perte d'entraînement** | L'erreur sur l'exemple qu'il vient de lire. Elle saute beaucoup d'un pas à l'autre (exemples faciles ou difficiles) : on ne la lit pas seule. |
| **Erreur de validation** | L'erreur moyenne sur les exemples **mis de côté**. C'est le vrai thermomètre : si elle baisse, il comprend ; si elle remonte, il apprend par cœur. |
| **Surapprentissage** | Le modèle récite ses exemples au lieu de généraliser : la perte d'entraînement baisse encore, l'erreur de validation remonte. |
| **Arrêt anticipé, patience** | On mesure l'erreur de validation tous les 20 pas. Si elle est au-dessus de la meilleure **2 fois de suite** (patience = 2), on arrête. Deux fois, pour ne pas s'arrêter sur un simple hasard. |
| **Meilleure sauvegarde** | À chaque nouvelle meilleure erreur de validation, le calque est enregistré à part (dossier « meilleur »). C'est **lui** qu'on exporte, pas le dernier. |
| **Export (GGUF, Q4_K_M)** | Le modèle + son calque sont fusionnés puis compressés (2,5 Go) au format que lit Ollama, le moteur qui fait tourner le modèle sur le PC. |
| **Parties** | Colab et Kaggle gratuits peuvent couper : l'entraînement est découpé en parties qui reprennent là où la précédente s'est arrêtée. |

## 4. Les trois entraînements, dans l'ordre

### Essai 1 — 23/11 au soir, Colab (GPU T4 gratuit) : raté, mais utile

- **Données** : 33 exemples d'entraînement, 7 de validation, 13 de test.
- **Déroulé** : 25 pas ; erreur de validation 0,297 puis 0,255 (elle baissait : pas de surapprentissage).
- **Test** : le modèle répondait **vide** 9 fois sur 13 (la base : 13 sur 13 justes).
- **Cause trouvée** : dans les exemples, les champs de la réponse étaient dans l'ordre « statut, preuve manquante,
  phrases ». Ollama impose l'ordre « statut, phrases, preuve manquante ». Le modèle, forcé d'écrire dans un ordre
  jamais vu, abandonnait les phrases.
- **Ce qu'on a appris** : (1) les exemples doivent suivre **exactement** le format que l'application impose ;
  (2) **tester avant de télécharger** : ce test a évité de rapatrier 5 Go inutiles ; (3) 33 exemples, c'est trop peu.

### v4 — 24/11, Colab (T4) : réussi, adopté

- **Données** : 535 exemples (341 / 25 / 169), tirés des rapports de la Cour des comptes européenne 2023-2026 et des
  réponses de la Commission ; 5 tâches : extraction, position, conflit, feuille de route, refus.
- **Déroulé** (85 pas par époque) :

| Pas | 20 | 40 | 60 | **80** | 85 | 100 |
|---|---|---|---|---|---|---|
| Erreur de validation | 0,245 | 0,188 | 0,166 | **0,165 (meilleure)** | 0,172 | 0,181 → arrêt |

- **Pourquoi le pas 80** : c'est la plus basse erreur sur les exemples mis de côté. Ensuite elle remonte deux fois
  (85, puis 100) : le modèle commençait à réciter. L'export a pris le pas 80.
- **Pourquoi la partie 3 n'a rien fait** : l'arrêt était déjà décidé ; continuer aurait gaspillé du quota et abîmé
  le modèle. Durée réelle : ~21 min d'entraînement au lieu des 1 h 30 à 3 h prévues.
- **Test (169 exemples jamais vus), base → v4** : choix « répondre ou refuser » 114 → 168 ; refus quand rien ne le
  permet 4 → 31 sur 31 ; extraction 3 → 31 sur 31 ; position 46 → 50 sur 50 ; conflit 11 → 11 sur 24.
- **Ce qu'on a appris** : l'entraînement change vraiment le **comportement** (refus, extraction) ; il ne suffit pas
  pour une tâche **difficile et rare** dans les données (le conflit : 35 exemples seulement).

### v5 — 25/11, Kaggle (T4) : réussi, mais pas meilleur que v4

- **Pourquoi** : sur un vrai rapport, le modèle ne trouvait que 2 axes. On a ajouté la tâche « axes » : 140 exemples
  dont la bonne réponse vient du **sommaire** des rapports (chaque grande partie des observations = un axe choisi par
  les auditeurs). Paquet : 675 exemples (441 / 29 / 205), **même découpage par rapport** que v4 pour comparer.
- **Déroulé** (111 pas par époque, 43 min d'entraînement) :

| Pas | 20 | 40 | 60 | 80 | 100 | 111 | **120** | 140 | 160 |
|---|---|---|---|---|---|---|---|---|---|
| Erreur de validation | 0,283 | 0,201 | 0,176 | 0,167 | 0,156 | 0,165 | **0,155 (meilleure)** | 0,161 | 0,159 → arrêt |

- **Pourquoi le pas 120** : plus basse erreur de validation ; le calque de ce moment est enregistré à part, dans
  « meilleur », et c'est lui qui est exporté.
- **Pourquoi 40 pas de plus, jusqu'à 160** : on ne mesure que tous les 20 pas, et on attend **deux** remontées de
  suite : au pas 140 (1/2), puis au pas 160 (2/2). L'arrêt tombe donc à 160, mais on garde 120.
- **Pourquoi la partie 3 n'a rien fait** : même raison que v4, l'arrêt était déjà décidé.
- **Pourquoi la perte d'entraînement saute (0,017 à 0,295)** : chaque pas ne voit que 4 exemples, faciles ou non ;
  seule l'erreur de validation, moyenne sur des exemples fixes, se lit.
- **Test (205 exemples), base → v5** (v4 entre parenthèses quand il existe) :

| Tâche | Base | v5 | (v4) |
|---|---|---|---|
| Refus justes | 4/31 | 29/31 | (31/31) |
| Extraction | 3/31 | 31/31 | (31/31) |
| Position | 46/50 | 49/50 | (50/50) |
| Conflit | 11/24 | 11/24 | (11/24) |
| Axes : paires de constats bien rangées | 430/779 (55 %) | 447/779 (57 %) | — |

- **Lecture** : v5 ≈ v4 (les écarts de 1 ou 2 exemples sont du bruit). Les axes progressent à peine au-dessus du
  hasard (~50 % avec 2 ou 3 axes) : 100 exemples ne suffisent pas pour une tâche aussi difficile, et une phrase isolée
  ne dit souvent pas à quelle partie d'un rapport elle appartient.
- **Décision** : garder v4 (déjà installé, équivalent) ; ne pas refabriquer v5. Le fichier final de v5 n'a pas été
  téléchargé (session Kaggle arrêtée avant l'export) ; son calque du pas 120 reste dans la version Kaggle enregistrée.
- **Ce qu'on a appris** : (1) notre chaîne d'entraînement est **stable et reproductible** (même schéma deux fois) ;
  (2) certaines tâches se règlent mieux **par le code** que par l'entraînement : depuis le 25/11, l'application
  range les constats par le sens (comparaison de vecteurs), et le modèle ne fait que **nommer** chaque axe.

## 5. Ce que les trois essais nous ont appris, en résumé

1. **Le format compte plus que tout** : un ordre de champs différent suffit à rendre le modèle muet (essai 1).
2. **Peu d'exemples, mais justes, suffisent pour un comportement** (refuser, citer, extraire : 341 exemples, 21 min).
3. **Une tâche difficile demande beaucoup d'exemples** (conflit, axes) : 35 ou 100 ne suffisent pas.
4. **L'arrêt anticipé protège** contre l'apprentissage par cœur ; on exporte toujours la meilleure version.
5. **On mesure avant d'adopter** : test sur des rapports jamais vus, puis test dans l'application, puis vrai rapport.
6. **Le code et le modèle se complètent** : le code range et vérifie (fiable), le modèle lit et rédige (souple).

## 6. Limites de Colab et de Kaggle gratuits (mesurées)

| | Colab gratuit | Kaggle gratuit |
|---|---|---|
| GPU | T4 (16 Go) | T4 ×2 (un seul utilisé) |
| Quota | non publié ; consommé même quand le GPU ne calcule pas | ~30 h par semaine, affiché dans le profil |
| Coupure | possible à tout moment | session de 12 h au plus |
| Sauvegarde | Google Drive | `/kaggle/working`, gardé seulement si « Persistence : Files only » ou version enregistrée **après** l'export |
| Durée v4 / v5 | 21 min d'entraînement (+ ~30 min de préparation) | 43 min d'entraînement (+ ~30 min de préparation) |

**Leçon pratique (25/11)** : enregistrer une version (**Save Version**) ou télécharger les fichiers **avant** d'arrêter
la session ; sinon les exports faits après la dernière version sont perdus.

## 7. Le carnet d'entraînement, cellule par cellule (Colab et Kaggle)

Les deux carnets (`training/colab/cadrage_entrainement.ipynb`, `training/kaggle/cadrage_entrainement_kaggle.ipynb`)
sont **générés** par `make_notebook.py` / `make_notebook_kaggle.py` : mêmes étapes, seuls le stockage et quelques
chemins changent. Chaque cellule appelle le code du dépôt, figé à une version précise (`CODE`), et un paquet de données
vérifié par son empreinte (`DONNEES`).

| Cellule | Ce qu'elle fait | Pourquoi |
|---|---|---|
| Étape 1 · vérifier | GPU présent, Internet, place disque ; sur Kaggle, reprend l'état d'une version enregistrée | ne pas dépenser de quota pour rien |
| Étape 2 · code et données | télécharge le dépôt à la version `CODE` et le paquet de données, **refuse** si l'empreinte SHA-256 diffère | entraîner exactement sur les données relues |
| Étape 3 · bibliothèques | installe PyTorch, Transformers, PEFT (LoRA), bitsandbytes (4 bits), TRL… aux versions figées | reproductibilité |
| Étape 4 · modèle de base | télécharge Qwen3-4B à une révision précise (8 Go) | toujours le même point de départ |
| Étape 5 · Ollama | installe Ollama et compare son gabarit de conversation avec celui de l'entraînement | sinon le modèle entraîné ne « reconnaît » pas les questions (leçon de l'essai 1) |
| Étape 6 · llama.cpp | compile l'outil qui compresse le modèle (Q4_K_M) | fichier de 2,5 Go lisible par Ollama |
| Étape 7 · lanceur | prépare la commande `cadrage(...)` des cellules suivantes | une ligne par cellule, lisible |
| Partie 0 · preuve | 2 pas d'entraînement, reprise, export complet, réponse JSON vérifiée | prouver toute la chaîne **avant** l'entraînement long |
| Parties 1 à 3 | l'entraînement, en tiers qui **reprennent** là où le précédent s'est arrêté ; mesure de validation tous les 20 pas, arrêt anticipé, meilleure version sauvée à part | survivre aux coupures de Colab / Kaggle |
| Où j'en suis | affiche pas, pertes, meilleure validation | suivre sans rien lancer |
| Exporter le modèle entraîné | fusion LoRA + base → GGUF f16 → Q4_K_M → empreinte | le fichier à importer dans Ollama |
| Exporter la base | la **même** chaîne sur le modèle sans LoRA | comparer à armes égales |
| Résumé | pas, courbes, durée, fichiers à télécharger et leurs empreintes | savoir quoi rapatrier |
| Test avant téléchargement | base contre LoRA sur les exemples de test, par tâche | ne télécharger que si c'est mieux |

**Fichiers du dépôt utilisés** : `training/profiles/colab-parties.yaml` (réglages : rang 16, taux 1e-4, lots de 4,
3 époques au plus, patience 2), `training/parts.py` (parties, reprise, meilleure version), `training/train_lora.py`
(boucle QLoRA), `training/export_gguf.py` (fusion et compression), `training/import_ollama.py` (import sur le PC avec
vérification des empreintes), `training/dataset/*` (construction des exemples), `training/colab/test_avant_telechargement.py`
(le test final), `training/registre/*.json` (le registre lu par le tableau de bord).

## 8. Comment sait-on qu'une réponse est « bonne » ?

**Ce n'est pas en comparant avec ce que l'assistant de code aurait répondu.** La « bonne réponse » de chaque exemple
vient des **documents publics eux-mêmes**, découpés par des programmes :

| Tâche | D'où vient la bonne réponse |
|---|---|
| Extraction de constats | phrases **recopiées** des paragraphes du rapport qui énoncent un constat (« nous avons constaté », « n'a pas »…) ; thème et gravité attribués par des règles écrites dans le code |
| Position (accepte / partiellement / rejette) | la **réponse officielle de la Commission** à chaque recommandation, publiée avec le rapport |
| Conflit | une réponse « partiellement » ou « rejette » de la Commission, dont la justification sert de contrainte ; « aligné » si elle accepte (règle simple : 2 exemples de test se sont révélés mal étiquetés) |
| Feuille de route | les recommandations du rapport et leurs **échéances officielles** (« Quand ? »), recopiées |
| Refus | on **retire** le passage qui contient la réponse : la bonne réponse devient « preuves insuffisantes » |
| Axes | le **sommaire** du rapport : les grandes parties écrites par les auditeurs |

Les exceptions, dites franchement : les **28 exemples du pilote v2**, rédigés par programme puis relus et corrigés
par l'assistant (6 corrigés) ; les règles de thème et de gravité ; et, dans le test sur le vrai rapport, les **8 paires
de conflit** construites à partir d'une fiche de stratégie fictive. Là, la bonne réponse a été fixée à la main.

**Comment on note** : sans jugement subjectif. Le programme de test compare le **statut** (répondre ou refuser),
l'**étiquette** (accepte, conflit…), et passe chaque phrase produite au **vérificateur de l'application** (la source
citée existe-t-elle, les chiffres y figurent-ils ?). Pour les axes, il compare les **paires** de constats rangées
ensemble ou séparées. Le banc dans l'application (31 sections) utilise un corpus fictif dont les faits et les
sections « sans preuve » sont connus d'avance.
