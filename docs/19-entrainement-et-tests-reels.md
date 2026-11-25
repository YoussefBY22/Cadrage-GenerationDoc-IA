# 19 — Entraînement du modèle, tests sur un vrai rapport, feuille de route par axes (23/11 soir → 24/11/2026)

> Lecteur : toi, ton encadrant, ou un technicien qui reprend le projet. Suite de
> [`18-rapport-technique-detaille.md`](18-rapport-technique-detaille.md) (21 au 23/11). Les mots techniques sont
> expliqués au §1. Chaque chiffre vient d'une mesure faite sur Colab ou sur le PC (GTX 1650, 4 Go), jamais d'une
> estimation. Fichiers de résultats : dossier de travail de l'orchestrateur (non versionné, car ils citent des
> documents entiers), recopiés ici en tableaux.

## En bref

| Question | Réponse courte |
|---|---|
| Qu'a-t-on entraîné ? | Qwen3-4B (le modèle de l'application), avec une LoRA, sur 341 exemples publics de la Cour des comptes européenne. |
| Combien de temps ? | 21 min d'entraînement sur le GPU gratuit de Colab (T4), arrêt automatique au bon moment. |
| Est-il meilleur ? | Oui, nettement, sur ce qu'on lui a appris : refuser sans preuve, extraire des constats, lire la position d'une institution, citer juste. |
| Qu'est-ce qui ne marche pas encore ? | Détecter un vrai conflit entre une recommandation et une stratégie ; calibrer la gravité ; traiter un rapport réel de 100 pages en une seule feuille de route. |
| Le produit marche-t-il sur un vrai rapport ? | Oui depuis la feuille de route **par axes** (§9, PR #21) : 55 constats traités en 27 min dans la fenêtre de 4 096 jetons. Avant, elle **bloquait** (§6) ; agrandir la fenêtre à 8 192 jetons était trop lent sur ce PC (§7). |
| Et ensuite ? | Le modèle trouve encore trop peu d'axes : la tâche « axes » est ajoutée au jeu d'entraînement (paquet v5, §10, PR #22). Prochain entraînement : Kaggle. |

## 1. Les mots à connaître

| Mot | Ce que ça veut dire, simplement |
|---|---|
| **Modèle de base** | Qwen3-4B tel qu'il est publié (4 milliards de paramètres). Il sait écrire du français, mais ne connaît pas nos règles. |
| **Entraînement LoRA / QLoRA** | On ne réécrit pas le modèle : on lui ajoute un petit « calque » de réglages (~1 % de sa taille) qu'on entraîne sur nos exemples. QLoRA = la même chose avec le modèle compressé en 4 bits pour tenir sur un petit GPU. |
| **Exemple d'entraînement** | Une consigne (« voici des passages, extrais les constats ») + la bonne réponse attendue, écrite à partir de documents réels. |
| **Train / val / test** | Train : exemples appris. Val : exemples mis de côté pour savoir quand arrêter. Test : exemples **jamais vus**, pour la note finale. |
| **Pas, époque** | Un pas = le modèle voit 4 exemples et se corrige. Une époque = il a vu tous les exemples une fois (ici 85 pas). |
| **Erreur de validation** | Combien le modèle se trompe sur les exemples « val ». Elle doit baisser ; si elle remonte, il apprend par cœur (surapprentissage). |
| **Arrêt anticipé** | Si l'erreur de validation remonte 2 fois de suite, on arrête et on garde la meilleure version. |
| **GGUF, Q4_K_M** | Le format de fichier qu'Ollama sait lire, compressé à ~4 bits par poids : 2,5 Go au lieu de ~8 Go. |
| **Ollama** | Le moteur qui fait tourner le modèle sur le PC. Ce n'est pas le modèle : c'est le « lecteur » du modèle. |
| **Jeton (token)** | Le morceau de texte que lit le modèle. En français, 1 jeton ≈ ¾ de mot ; 1 000 mots ≈ 1 400 jetons. |
| **Fenêtre de contexte** | La **mémoire de travail** du modèle pour une seule question : consigne + documents fournis + sa réponse. Tout ce qui dépasse n'est pas lu. Dans l'application : 4 096 jetons ≈ 3 000 mots ≈ 6 pages (§6). |
| **TPV** | Part des phrases produites qui sont vérifiées par le vérificateur (la source existe et dit bien ça). |
| **Refus** | Le modèle répond « preuves insuffisantes » au lieu d'inventer. C'est voulu quand les documents ne disent rien. |
| **Banc** | Notre batterie de tests automatique, rejouée à l'identique sur chaque modèle. |

## 2. Les données d'entraînement (jeu v4)

- **Source** : rapports spéciaux de la Cour des comptes européenne 2018-2026 et réponses officielles de la Commission
  (licence CC BY 4.0, réutilisation autorisée avec citation). Aucun document client.
- **Pourquoi cette source** : chaque rapport contient des recommandations **et** la réponse de l'institution
  auditée (« accepte », « accepte partiellement », « rejette » + justification). C'est exactement ce qu'on veut
  apprendre : comprendre une recommandation face aux priorités et contraintes de l'organisation.
- **Volume** : 535 exemples = 341 entraînement, 25 validation, 169 test. Les rapports du test sont différents de
  ceux de l'entraînement (pas de fuite).
- **Répartition des 341 exemples d'entraînement** :

| Tâche | Exemples | Ce qu'on apprend |
|---|---|---|
| Position | 92 | lire si l'institution accepte, accepte partiellement ou rejette, et pourquoi |
| Refus | 76 | dire « preuves insuffisantes » quand les passages ne répondent pas |
| Extraction de constats | 73 | lister les faits observés, un par ligne, avec gravité et source |
| Feuille de route | 47 | regrouper des constats en initiatives reliées aux priorités |
| Conflit | 35 | dire si une recommandation contredit une stratégie, en citant les deux |
| Autres / TdR-CdC | 18 | rédaction de sections |

- **Défauts connus du jeu** : seulement 35 exemples de conflit (trop peu) ; 2 exemples de test « conflit »
  mal étiquetés ; très peu d'exemples de rédaction TdR/CdC.

### L'essai raté d'avant (23/11 soir) et ce qu'il a appris

Un premier entraînement sur 33 exemples a donné un modèle qui répondait **vide** 9 fois sur 13. Cause : dans les
exemples, les champs JSON étaient dans l'ordre `status, missing_evidence, sentences`, alors qu'Ollama impose
l'ordre `status, sentences, missing_evidence`. Le modèle, forcé d'écrire dans un ordre qu'il n'avait jamais vu,
abandonnait les phrases. Corrigé dans le jeu v4 (ordre identique au schéma), et le test sur Colab **avant**
téléchargement a évité de rapatrier 5 Go inutiles.

## 3. L'entraînement (24/11, Colab gratuit, GPU T4)

**Réglages** (`training/profiles/colab-parties.yaml`) : QLoRA 4 bits, rang 16, taux d'apprentissage 1e-4,
lots de 4, au plus 3 époques, exemples coupés à 2 048 jetons, mesure de validation tous les 20 pas, arrêt après
2 remontées.

| Étape | Durée | Ce qui s'est passé |
|---|---|---|
| Préparation + partie 0 (essai d'export) | ~30 min | vérifie toute la chaîne sur 2 pas avant de dépenser le quota |
| Partie 1 (pas 1 → 86) | 18 min (≈ 12 s par pas) | erreur de validation 0,245 → 0,188 → 0,166 → **0,165 au pas 80 (meilleure)** → 0,172 |
| Partie 2 (pas 86 → 100) | 3 min | 0,181 : 2ᵉ remontée → **arrêt anticipé au pas 100** |
| Partie 3 | 4 s | rien à faire, arrêt déjà décidé |
| Export LoRA + export base | — | 2 fichiers GGUF de 2,5 Go ; la base passe par la même chaîne pour une comparaison juste |
| Test sur Colab (169 × 2 modèles) | ~35 min (≈ 6 s par exemple) | §4 |

**Lecture** : le modèle a appris en ~1 époque, puis a commencé à apprendre par cœur. L'arrêt anticipé a gardé la
version du pas 80. Les limites de Colab gratuit (quota non publié, consommé même quand le GPU ne calcule pas,
déconnexion possible) ont imposé le découpage en parties qui reprennent là où la précédente s'est arrêtée.

**Retour sur le PC** : l'import dans Ollama a d'abord été refusé (« gabarit différent »). Ce n'était pas une
vraie différence : Ollama réordonne les lignes de paramètres. La comparaison ignore maintenant l'ordre
(`training/export_gguf.py`, `same_template`, avec un test ; PR #20). Les deux fichiers téléchargés avaient été
intervertis : identifiés par leur empreinte SHA-256 et remis à leur place.

## 4. Résultat 1 — test sur Colab (169 exemples jamais vus)

| Mesure | Base | Entraîné |
|---|---|---|
| Choix juste « répondre ou refuser » | 114/169 | **168/169** |
| Refus quand il n'y a pas de preuve | 4/31 | **31/31** |
| Extraction de constats réussie | 3/31 | **31/31** |
| Position juste (accepte / partiellement / rejette) | 46/50 | **50/50** |
| Phrases vérifiées | 536/542 | 553/554 |
| Erreurs bloquantes | 5 | 1 |
| Conflit juste | 11/24 | 11/24 |

Le conflit est le point faible : sur ~14 vrais conflits, chacun n'en voit que 3 ; l'entraîné répond « aligné »
10 fois à tort. Cause probable : 35 exemples seulement, et des conflits souvent implicites dans les rapports.

## 5. Résultat 2 — banc dans l'application (31 sections, PC)

Même banc que le 23/11 (1 institution fictive, 11 sections de gabarits, 10 sections avec preuve, 10 sans preuve,
5 pièges), rejoué avec chaque modèle, 5 min de repos du GPU entre les deux (85-91 °C en charge).

| Mesure | Base | Entraîné |
|---|---|---|
| Refus manqués (a écrit alors qu'il n'y avait rien) | 40 % | **10 %** |
| Faux refus (a refusé alors qu'il y avait la preuve) | 0 % | 0 % |
| TPV | 95 % | **100 %** |
| Citations valides / chiffres fidèles | 99 % / 97 % | **100 % / 100 %** |
| JSON valide | 97 % | **100 %** |
| Pièges (consigne cachée) suivis | 0/5 | 0/5 |
| Temps par section : médian / lent (p95) | 20 s / 37 s | **18 s / 24 s** |
| Mémoire GPU | 3,1 Go | 3,1 Go |

Remarque : le banc ne passe pas par le filtre de pertinence de l'application (qui refuse avant d'appeler le
modèle) : il mesure le modèle seul.

**À surveiller** : l'entraîné refuse 7 sections de gabarit sur 11 (profil, évaluation, exigences fonctionnelles et
non fonctionnelles, recette…) que la base remplissait. Ces sections demandent des **décisions** (profil
recherché, critères de recette) qu'un rapport de diagnostic ne contient pas : ces refus sont plutôt justes. À
confirmer avec une fiche de contexte remplie.

## 6. Résultat 3 — un vrai rapport, de bout en bout

**Document** : rapport spécial 17/2022 de la Cour des comptes européenne, « Consultants externes à la Commission »
(PDF officiel, 125 000 caractères ≈ 100 pages), avec les réponses officielles de la Commission. Jamais vu à
l'entraînement. Pour tester le conflit, l'orchestrateur a écrit une **fiche de stratégie fictive** (clairement
marquée comme telle) : 4 orientations qui contredisent une recommandation, 4 qui l'appuient.

### 6.1 Comprendre les recommandations

| Test | Base | Entraîné |
|---|---|---|
| Position de la Commission sur les 4 recommandations (vérité : « accepte ») | 4/4 | 4/4 |
| Conflit recommandation / stratégie (8 paires) | 8/8 | 7/8 |
| Phrases vérifiées | toutes | toutes |

L'entraîné rate un conflit (recommandation 1 contre « chaque direction reste libre ») et dit « aligné » : même
penchant qu'au test Colab. Les paires écrites à la main sont très explicites : ce test est plus facile que la
réalité.

### 6.2 Extraire les constats (112 morceaux de texte)

| | Base | Entraîné |
|---|---|---|
| Durée | 39 min | **13 min** |
| Morceaux en échec | 14/112 | **0/112** |
| Constats | 93 (doublons, 1 consigne recopiée comme constat) | 55 |
| Gravité | variée | presque tout « faible », même des lacunes graves |
| Défauts communs | — | phrases de méthode prises pour des constats (« Nous avons recueilli… ») |

Les deux modèles tirent aussi des « constats » des **réponses de la Commission** (« La Commission accepte… »).
Ce n'est pas un constat d'audit : ce document devrait servir à la position, pas à l'extraction. C'est un défaut de
l'application, pas du modèle.

### 6.3 La feuille de route bloque : ce que ça veut dire

Pour faire la feuille de route, l'application envoie au modèle, **en une seule question** : la consigne, tous les
constats validés, les priorités et les projets. Avec ce vrai rapport, cela faisait :

- base : 93 constats ≈ **5 860 jetons** ;
- entraîné : 55 constats ≈ **4 500 jetons**.

La fenêtre est de **4 096 jetons**, réponse comprise. Ça ne rentre pas. Plutôt que de couper des constats en
silence (le modèle ferait alors une feuille de route avec la moitié du rapport sans le dire), l'application
**refuse** avec un message clair (code `CONTEXT_FULL`, ajouté le 22/11, PR #7) : « réduisez les constats ou
choisissez un modèle à plus grande fenêtre ». C'est ça, « bloquer » : un arrêt propre et volontaire, pas un plantage.

Essai en ne validant que les constats graves (ce que ferait un consultant qui trie) :

| | Base | Entraîné |
|---|---|---|
| Constats gardés | 35 → ~2 850 jetons + consigne : encore trop | 13 → feuille de route en 5 min |
| Initiatives | — | 3, mais 2 au titre identique |
| Constats non rattachés | — | 9 sur 13 |
| Durées | — | aucune |

### 6.4 TdR (modèle entraîné, première initiative)

| Section | Résultat | Commentaire |
|---|---|---|
| Contexte | rédigée, 10 phrases, TPV 0,7 | 1 phrase sans source (titre recollé à un constat) |
| Objectifs | refusée | à tort : les recommandations donnent les objectifs |
| Profil | refusée, « décision humaine requise » | juste : c'est au consultant de décider |
| Calendrier | refusée, « décision humaine requise » | juste |

## 7. La fenêtre de contexte : pourquoi 4 096, et comment l'augmenter

**Ce n'est pas une limite du modèle.** Qwen3-4B sait lire 32 768 jetons. Ce n'est pas non plus une limite
d'Ollama. C'est un **réglage de l'application** (`app/llm/ollama.py`, `DEFAULT_NUM_CTX = 4096`, modifiable par
la variable `OLLAMA_NUM_CTX`), choisi le 22/11 pour que tout tienne dans les 4 Go de la GTX 1650.

**Pourquoi la mémoire GPU limite** : pour chaque jeton lu, le modèle garde en mémoire un « carnet de notes » (le
cache KV) pour pouvoir y revenir. Pour Qwen3-4B, c'est environ 144 Ko par jeton (36 couches × 8 têtes × 128 ×
2 × 2 octets). Donc :

| Fenêtre | Carnet de notes | + modèle (2,5 Go) | Mesuré avec `ollama ps` sur le PC |
|---|---|---|---|
| 4 096 | ~0,6 Go | ~3,1 Go | 3,5 Go au total, **34 % sur le processeur** / 66 % GPU |
| 8 192 | ~1,2 Go | ~3,7 Go | 4,2 Go, 45 % processeur / 55 % GPU |
| 16 384 | ~2,3 Go | ~4,8 Go | 5,4 Go, 56 % processeur / 44 % GPU |

Quand ça ne tient pas dans la carte, Ollama met le reste sur le processeur et la mémoire du PC : **ça marche,
mais plus lentement**. On n'est donc pas bloqués par un mur, mais par la vitesse. Comparaison : Claude, ici, a
une fenêtre de 1 million de jetons, mais tourne sur des serveurs avec des dizaines de Go de mémoire par GPU ;
notre modèle tourne sur une carte de 4 Go, sur site, sans rien envoyer dehors.

**Les solutions, de la plus simple à la plus solide** :

1. **Monter la fenêtre à 8 192** (`OLLAMA_NUM_CTX=8192`). **Essayé le 24/11** avec les 55 constats de
   l'entraîné : la demande rentre (plus de refus `CONTEXT_FULL`), mais le modèle, à moitié sur le processeur,
   n'a pas fini en 5 min, et l'application a coupé deux fois (délai `LLM_TIMEOUT_SECONDS=300`, 604 s au
   total, erreur `MODEL_INVALID`). Seule, cette solution ne suffit donc pas sur ce PC.
2. **Compresser le carnet de notes** : Ollama sait stocker le cache en 8 bits au lieu de 16
   (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`) : 8 192 jetons pour la mémoire de 4 096
   aujourd'hui, avec une perte de qualité généralement faible (à mesurer sur notre banc).
3. **Ne plus tout envoyer d'un coup** (la vraie solution, indépendante du matériel) : fusionner les doublons,
   regrouper les constats par thème (le code le fait avec les vecteurs bge-m3, sans modèle), faire une
   proposition d'initiatives **par thème**, puis une dernière passe courte qui ordonne les initiatives. Ainsi
   un rapport de 300 pages passe aussi bien qu'un de 10.
4. **Plus de matériel** chez le client (GPU 12-24 Go) : 16 000 à 32 000 jetons sans ralentir. Hors de portée du
   PC de développement.

## 8. Ce qu'il faut faire ensuite, par ordre d'impact

| # | Action | Type | Pourquoi |
|---|---|---|---|
| 1 | ~~Regrouper les constats par thème avant la feuille de route~~ **fait** (§9, PR #21) | code | seul vrai blocage sur un rapport réel |
| 2 | Activer le cache 8 bits et mesurer 8 192 jetons sur le banc | réglage + mesure | double la fenêtre sans racheter de matériel |
| 3 | Ne pas extraire de constats des réponses de l'institution | code | elles servent à la position |
| 4 | ~~Interdire deux initiatives au même titre~~ **fait** (§9) ; rattacher chaque constat (6 sur 55 encore sans initiative) | code | défauts vus en 6.3 et 9 |
| 5 | Entraînement suivant (Kaggle, quota hebdomadaire plus large) : tâche « axes » **prête** (§10) ; à ajouter : plus de vrais conflits, gravité équilibrée, « phrase de méthode ≠ constat », objectifs tirés des recommandations, corriger les 2 étiquettes | données + entraînement | points faibles vus en 4, 6.1, 6.2, 6.4 |
| 6 | Tester sur tes propres rapports, puis recalibrer le filtre de pertinence (seuil 0,45) sur ces données | mesure | le seuil a été réglé sur des données fictives |

**Proposition (à valider par Youssef)** : utiliser le modèle entraîné (`cadrage-4b-lora`) par défaut pour
l'extraction, la position et le refus, en gardant la base (`cadrage-4b-base`) importée à côté pour comparer.

## 9. Feuille de route par axes (24/11, PR #21)

**Ce que font les cabinets** (sources publiques : McKinsey, guide PEFA de la Banque mondiale, cabinets français ;
rien de public sur la méthode propre à EY) : une feuille de route se lit sur deux dimensions, des **axes** (chantiers :
gouvernance, processus, systèmes d'information, données…) et des **horizons** (gains rapides, fondations,
transformation), ordonnés selon la valeur, la faisabilité, les dépendances, en commençant par les bases.

**Ce que fait maintenant l'application** : au lieu d'une seule grosse question, plusieurs petites, chacune sous la
fenêtre de 4 096 jetons.

| Étape | Qui | Détail |
|---|---|---|
| 1. Doublons | code | constats quasi identiques fusionnés (≥ 85 % de mots communs), sans rien perdre |
| 2. Axes | modèle, lots de 25 constats | il déclare les axes nouveaux une fois (A1 : titre), puis donne l'axe de chaque constat selon son sens ; les axes déjà créés lui sont rappelés |
| 3. Initiatives | modèle, axe par axe | au plus 8 constats et 4 initiatives par appel ; une partie ratée est signalée, les autres sont gardées |
| 4. Classement, vagues | code | inchangé : score, rang, vagues, chemin critique |
| TdR / CdC | code | une section ne reçoit que les constats de **son** initiative (avant : les 55, soit 17 000 caractères, refus d'Ollama) |
| Écran | interface | tableau **axes × vagues** |

**Mesure sur le vrai rapport** (cadrage-4b-lora, 55 constats, fenêtre 4 096) :

| | Avant | Après |
|---|---|---|
| Feuille de route | refusée ; à 8 192 jetons, coupée après 604 s | **produite** en 1 651 s (~27 min), 12 initiatives |
| Appels au modèle | 1 (trop gros) | 3 « axes » (30-60 s) + 9 « initiatives » (2-4 min) |
| TdR « contexte » | TPV 0,7, puis refus d'Ollama | **TPV 1,0** en 70 s |
| Défauts restants | — | 2 axes seulement ; 1 partie sur 9 ratée ; 6 constats sans initiative ; une initiative nommée « Données » |

Tests : 726 backend, 12 interface. Détail : `docs/lots/AXES.md` (branche de la PR #21).

## 10. Tâche « axes » pour le prochain entraînement (24/11, PR #22)

**Problème** : le modèle entraîné n'a jamais appris à ranger des constats en axes (2 axes au lieu de 3 à 7).

**Vérité utilisée** : le **sommaire** de chaque rapport de la Cour. Les observations y sont découpées en grandes
parties, chacune avec sa plage de points (ex. « 18 - 32 », « 33 - 56 »). Un constat recopié du point 40 appartient
à la partie 33-56. Ce sont les auditeurs qui ont fait ce regroupement : rien n'est inventé. Les constats sont
**mélangés** pour que le modèle range selon le sens, pas selon la place dans la liste (son défaut sur le vrai rapport).

| | Valeur |
|---|---|
| Rapports téléchargés (Cour des comptes UE 2023-2026, CC BY 4.0) | 89 ; sommaire lu sur 84 (formats 2022-2024 et 2025) |
| Exemples « axes » | 140 : 100 entraînement, 4 validation, 36 test |
| Paquet v5 | v4 inchangé (535) + 140 = **675 exemples**, **même découpage par rapport** (comparable à v4) |
| Longueur | 471 à 1 038 jetons par exemple (limite d'entraînement : 2 048) |
| Contrôles | aucun défaut ; invite identique à celle de l'application ; exemples relus par l'orchestrateur |
| Note au test final | paires de constats rangées ensemble ou séparées comme dans le sommaire ; axes obtenus / attendus |
| Carnets | Colab et Kaggle épinglés : CODE e20ddf3, DONNEES 5909f70d… |

**Limites** : les titres d'axe sont ceux des auditeurs (phrases jusqu'à 30 mots), pas des noms courts de cabinet ;
une source du pilote v3 a un certificat de sécurité expiré, la vérification n'a pas été contournée : le paquet v4 est
repris tel quel au lieu d'être reconstruit ; l'entraînement v5 n'a pas encore tourné.

## 11. Entraînement v5 (25/11, Kaggle) — résumé

Tout est expliqué pas à pas dans [`20-comprendre-l-apprentissage.md`](20-comprendre-l-apprentissage.md). En bref :
675 exemples (dont 140 « axes »), 43 min d'entraînement, meilleure erreur de validation 0,155 au pas 120, arrêt
anticipé au pas 160. Test sur 205 exemples : v5 ≈ v4 (refus 29/31, position 49/50, conflit 11/24) ; axes : 57 % des
paires de constats bien rangées (base 55 %), à peine mieux que le hasard. **Décision : on garde v4** ; le fichier v5
n'a pas été téléchargé (session arrêtée avant l'export), son calque reste dans la version Kaggle enregistrée.

## 12. Nuit du 24 au 25/11 : axes rangés par le code, parcours réel complet (v4)

**Changement de méthode** (leçon de v5) : le **code** range les constats par leur sens, le **modèle** ne fait que
nommer chaque axe. Le consultant peut aussi **imposer ses axes** dans la fiche de contexte (champ « Axes de la feuille
de route », proposé aussi par le chat) ; chaque constat va alors à l'axe le plus proche.

| Méthode de regroupement (74 vrais constats, vecteurs bge-m3) | Taille des axes |
|---|---|
| Hiérarchique (premier essai) | 58, 9, 3, 2, 1, 1 : un axe absorbe tout |
| **Vecteurs centrés + k-moyennes sphériques** (retenue) | 16, 15, 13, 11, 10, 9 |

Pourquoi centrer : tous les constats d'un même rapport partagent le même vocabulaire (« Commission »,
« consultants ») ; on retire cette partie commune pour ne garder que ce qui les distingue.

**Parcours réel** : rapport spécial 17/2022 (Cour des comptes européenne, 53 pages), modèle v4, GTX 1650, fenêtre
4 096. Extraction : 74 constats en 15 min. Trois passages de la feuille de route, corrigés entre chaque :

| Passage | Durée | Initiatives | Constats sans initiative | Parties perdues | Défauts vus → corrigés |
|---|---|---|---|---|---|
| 1 | 53 min | 17 | 16 | 1 | un axe de 58 constats ; un nom d'axe en boucle (17 500 caractères) ; un titre = la consigne recopiée → regroupement équilibré, longueurs bornées, titres recopiés écartés |
| 2 | 38 min | 16 | 19 | 2 | réponses tronquées (4 500 à 7 300 caractères) → 3 initiatives par appel, justifications courtes, réserve de 1 800 jetons, partie ratée coupée en deux et reprise |
| **3** | **24 min** | **21** | **11** | **0** | noms d'axe coupés à 80 caractères ; un axe nommé par défaut « constat d'audit » ; quelques titres-phrases |

**TdR et CdC** (même dossier) : « contexte » rédigé et vérifié (TPV 1,0) ; une même phrase répétée 6 fois → les
phrases identiques sont désormais retirées. « Objectifs » : rédigé au passage 3 (4 phrases, recommandations
reformulées), refusé à la régénération : le modèle n'est pas stable sur cette section. Profil, calendrier,
évaluation : « décision humaine requise » (voulu). **CdC : presque tout refusé** (« aucun passage ne contient
d'exigence ») : un rapport d'audit ne décrit pas un système à construire. Pour un vrai CdC, il faut les décisions et
exigences du consultant (fiche, décisions confirmées), ou un document de besoins.

**Captures** (interface, ce dossier) : dossier Google Drive « Cadrage IA — captures du 25-11-2026 ».

**Limites honnêtes à ce jour** : 24 min pour une feuille de route sur un PC à GPU de 4 Go ; 11 constats sur 74 sans
initiative ; titres parfois maladroits ; CdC vide sans exigences fournies par un humain.
