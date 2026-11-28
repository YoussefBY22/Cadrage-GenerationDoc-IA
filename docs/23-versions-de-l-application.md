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

Méthode : chaque réponse de l'IA est relue contre le rapport (RS 17/2022 de la Cour des comptes européenne,
53 pages), comme le ferait un consultant expert : la référence est-elle juste, la formulation fidèle, le
classement correct ? Pour chaque écart : se corrige-t-il **par le code** (V4.x) ou faut-il **entraîner** (V6) ?

### 4.1 Recommandations (règles, sans modèle)

| Élément | Attendu (rapport p. 42-45) | Obtenu | Verdict |
|---|---|---|---|
| Nombre | 4 recommandations | 4 | juste |
| Sous-points | n° 1 a-c, n° 2 a-d, n° 3 a-c, n° 4 aucun | identiques | juste |
| Échéances | « D'ici à décembre 2023 » ×4 | identiques | juste |
| Paragraphes cités | 18-26 et 24, 28-32 ; 34-36 et 38-56 ; 57-71 ; 72-84 | identiques | juste |

### 4.2 Nettoyage des constats (96 constats, modèle de base Qwen3-4B pour reformuler)

| Mesure | Résultat |
|---|---|
| Phrases de méthode, figures, cellules de tableau écartées | 31, toutes à juste titre sauf 1 (« contrôles de qualité supplémentaires », un point positif) |
| Doublons fusionnés (seuil 0,93) | 4 justes ; 2 paires restent (« les avait tous gérés… », deux phrases quasi identiques) |
| Reformulations fidèles et plus claires | ≈ 50 sur 59 actives |
| **Inventions** (sens ajouté ou changé) | ≈ 5 : n° 67 « ne vérifie pas correctement les données » (absent du rapport), n° 74 « n'a pas informé sur la manière dont elle évalue ses besoins » (inventé), n° 53 « la Commission a trouvé de bonnes pratiques » (ce sont les auditeurs), n° 61 « cela » mal résolu, n° 1 « informations » devenu « ne précise pas » |
| **Nature fausse** | ≈ 8 : règles et conditions (« si… elles doivent », « ne devraient jamais être externalisées »), principe général, contexte chiffré classés « problème » |
| Fautes de langue | 2 (« préviaient », « ne identifiaient ») |

**Ce que fait l'expert à la place** : il garde la phrase du rapport quand elle est claire, remplace seulement
le sujet implicite (« cela », « ces risques ») par ce qu'il désigne, et ne change jamais le verbe ni le sens.
Une règle ou une condition (« doivent », « sont censées », « si… ») décrit le cadre, pas un manque.

**Correction par le code (V4.2)** : contrôle de fidélité par le sens (reformulation trop éloignée de la phrase
d'origine → reformulation par règle), règles de nature (condition, obligation, principe général → contexte),
reformulation marquée « à relire ».

**Entraînement (V6), si le code ne suffit pas** : une tâche « reformuler un constat » dont la bonne réponse vient
du **rapport lui-même** : la synthèse (points I à IX) et la conclusion (points 85 à 91) d'un rapport de la Cour
reprennent en termes simples les constats du corps du texte ; ces couples (phrase détaillée → phrase de synthèse)
sont des exemples sans rédaction humaine, comme les autres tâches (doc 20 §8). Plus une tâche « nature »
(problème, positif, contexte) étiquetée par les marques du texte et vérifiée à la main sur un échantillon.

### 4.3 Test complet sur un nouveau dossier (V4.1 puis V4.2)

Parcours en images et relecture capture par capture : [`24-parcours-en-images.md`](24-parcours-en-images.md).

| Étape | Erreurs trouvées | Cause | Correction |
|---|---|---|---|
| Extraction (103 passages, 36 min) | 1 constat clé oublié (§ 90, diffusion fragmentée) ; **gravité incohérente** (même manque « élevé » en synthèse, « faible » dans le corps) ; titres de figure gardés | modèle | **entraînement** (gravité) ; règle « La figure N – » à ajouter |
| Nettoyage V4.2 (53 constats) | 1 glissement de sens, 1 **sens inversé**, 1 fusion fausse, 1 vrai constat écarté, « cela » non résolu | modèle + seuils | fusion : mots en commun exigés en plus du sens ; « échapper à » = manque ; le reste : **entraînement** (reformulation) |
| Règle de reformulation | « Il a été constaté que nous avons observé… », « que au », notes collées (« locaux14 ») | code | corrigé (V4.2) |
| Paragraphes | « § 82 » au lieu de 84 (numéro après une fin de phrase) ; « § 2 » (numéro de page) | code | corrigé (V4.2) |
| Feuille de route | sous-point sans constat placé avant un sous-point appuyé ; titre « La Commission devrait… » ; **R1 (le cadre, prérequis) en vague 3** | code ; gravité du modèle | code corrigé ; priorité : **entraînement** (gravité) + dépendances entre recommandations à prévoir |
| Feuille de route (usage) | impossible de régénérer ; impossible de choisir l'initiative d'un TdR | interface | « Régénérer » et « Rédiger les TdR / le cahier des charges » par initiative |
| TdR — Contexte | phrase abîmée (note de bas de page collée) **acceptée comme vérifiée** ; hors sujet ; voix des auditeurs | vérificateur ; recherche ; modèle | nettoyage des notes avant vérification (à faire) ; **entraînement** (contexte de mission) |
| TdR — Objectifs, Livrables | refus alors que la recommandation (transmise en P1) les contient | modèle | **entraînement** (recommandation → objectifs / livrables) |
| TdR — Méthodologie | refus **juste** (le rapport ne la décrit pas) | — | le consultant rédige, ou « Proposer quand même » |
| Proposition (modèle de base) | 8 objectifs : 3 répétitions, 2 hors périmètre | modèle de base | limiter le nombre ; **entraînement** |
| Cahier des charges — Exigences | refus du modèle entraîné ; proposition : 5 justes / 11, 1 doublon, **2 citent à tort une décision** | modèles | **entraînement** (exigences testables depuis une recommandation) ; contrôle : une décision ne peut être citée que pour sa catégorie |
| Interface | marques « [1] » et « D » dans l'éditeur ; la page TdR ne dit pas pour quelle initiative | interface | à faire |

### 4.4 Ce que le prochain entraînement (V6) doit apprendre, par ordre de priorité

1. **Gravité des constats** : même jugement pour un même manque, où qu'il soit dans le rapport. Bonnes réponses
   tirées du rapport : la conclusion (§ 85-91) reprend les manques que la Cour juge les plus importants.
2. **De la recommandation au livrable** : objectifs, livrables et exigences testables à partir du texte d'une
   recommandation et de ses sous-points (la recommandation est la source, sa reformulation la cible).
3. **Reformuler un constat** sans changer le sens ni le sujet (couples phrase du corps → phrase de la synthèse,
   comme au §4.2).
4. **Contexte de mission** : présenter le contexte d'une mission (chiffres et constats clés, cités) au lieu de
   recopier la voix des auditeurs.

Le reste se corrige par le code (V4.x) : règles, garde-fous, interface.
