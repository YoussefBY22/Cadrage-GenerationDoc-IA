# 05 — Revue critique du périmètre et du plan A à G

> Rédigé le 21/11/2026, après la phase A. Hypothèses non vérifiées marquées **« à vérifier »**.
> Décisions tranchées ici, reprises par `06` à `09`.

## 1. Verdict en une phrase

Le sujet est bon et défendable, mais le plan A–G fait **tout au même niveau d'effort**. Il faut **concentrer** le prototype sur ce qui le distingue d'un « ChatGPT local » : la **preuve** (chaque phrase reliée à un passage et vérifiée par du code) et la **mesure** (taux de phrases vérifiées, temps gagné). Le reste (éditeur riche, BI, LoRA) doit être **suffisant**, pas complet.

## 2. Ce qui est trop ambitieux (et ce qu'on en fait)

| Élément du plan | Risque | Décision |
|---|---|---|
| Éditeur TipTap complet : commentaires, comparaison de versions, restauration | 2 à 3 semaines de front à lui seul | **Garder** édition + sources cliquables + versions (liste, restauration). Comparaison = diff texte simple côté serveur. Commentaires = **un champ par section**, pas de fils. |
| LoRA « qui bat le RAG » | Petit modèle + peu de données publiques → gain incertain | **Garder comme expérience**, pas comme fonctionnalité. Conclusion honnête possible : « C ne bat pas B ». Le livrable est le **protocole** et les **scripts sûrs**. |
| Power BI **et** Metabase | Double travail | Power BI Desktop seul (vues + export CSV). Metabase = **une page de doc** + service Compose optionnel, pas de tableaux construits. |
| Import PPTX, export PPTX pour les 3 livrables | Faible valeur pour ToR/CdC | Import PPTX : texte des diapositives seulement. Export PPTX : **feuille de route uniquement**. |
| Reranking par modèle dédié | Téléchargement, GPU 4 Go déjà saturé | **Interface prête**, implémentation `NoopReranker`. Modèle de reranking = expérience serveur. |
| Chemin critique dans le graphe | Exige des durées fiables | Durées = estimation du consultant (champ), le modèle n'en invente pas. |
| Chiffrement au repos | Sujet d'exploitation, pas de code | Documenté (chiffrement du volume / disque), non codé. |
| Chiffres en toutes lettres, dates, unités | Explosion des cas | Normalisation des **nombres et pourcentages** FR/EN ; dates = années seulement ; le reste signalé « non vérifiable ». |

## 3. Ce qui manque

1. **Une couche de stockage abstraite** (imposée cette nuit : pas de Docker). → SQLAlchemy Core, une seule définition de tables, SQLite en test, PostgreSQL/pgvector en production (`06` §4).
2. **Une étape intermédiaire validable : les constats.** Le plan saute directement des documents aux livrables. Or le sujet dit « rapprocher les **constats** du diagnostic, les priorités et les dépendances ». → mode **« preuve d'abord »** (§4.1).
3. **Des gabarits de livrables** déclaratifs (sections, questions de recherche, nombre minimal de sources). FR-15 l'évoque ; il faut en faire le **pivot** : la génération est pilotée par le gabarit, l'export aussi, et la traduction anglaise devient un second jeu de gabarits.
4. **Un jeu d'évaluation « or »** (gold) dès la phase B, synthétique : sans lui, les critères « rappel » et « cas d'erreurs détectés à 100 % » ne sont pas mesurables.
5. **Authentification minimale et séparation des rôles** : « quatre yeux » (l'auteur ne peut pas approuver son propre livrable). Peu de code, fort effet devant un jury d'EY (contrôle interne).
6. **Sécurité de l'interface** : un document client peut contenir du HTML ou du Markdown piégé → affichage **échappé** côté front (XSS), pas seulement l'injection de prompt.
7. **Isolation par dossier vérifiée par test** : chaque requête de recherche filtre sur `dossier_id` ; un test prouve qu'aucun passage d'un autre dossier ne sort.
8. **Politique de conflit de fichiers entre développeurs parallèles** (cette nuit) : découverte automatique des routes, dépendances ajoutées en une fois (`09` §1).

## 4. Idées plus pertinentes pour le jury et pour EY

### 4.1 Mode « preuve d'abord » (recommandé : **cœur du produit**)
Trois étapes au lieu d'une :
1. **Extraction des constats** : le modèle lit les passages et produit des **fiches de constat** (texte court, thème, gravité, passages cités). Le vérificateur les contrôle ; le consultant **coche / corrige / supprime**.
2. **Feuille de route** construite à partir des **constats validés** : chaque initiative référence des constats ; les scores de priorité citent leurs preuves ; le calcul tranche.
3. **ToR et CdC** générés **par initiative** retenue, avec les constats et passages associés.

Gains : le modèle travaille sur des contextes courts (bon pour un modèle de 2 à 4 B), l'humain valide tôt, la traçabilité devient une **matrice constat → initiative → livrable** exportable. C'est la réponse directe à « rapprocher les constats ».

### 4.2 Indicateur phare : **taux de phrases vérifiées (TPV)**
`TPV = phrases « vérifiées » / phrases produites`. Une phrase est vérifiée si toutes ses sources existent, appartiennent au dossier, et si tous ses nombres figurent dans au moins une source citée. Affiché par section dans l'éditeur, agrégé dans le tableau de bord, comparé A/B/C/D. **Un chiffre unique, compréhensible par un associé EY.** Compléments : taux d'acceptation sans modification, distance d'édition, taux de refus justifiés.

### 4.3 Gabarits de livrables EY-compatibles
Gabarits YAML versionnés (`06` §5) : sections, consignes, questions de recherche, sources minimales, longueur. Un gabarit Word de référence (styles) par type. Permet de dire : « ajouter un nouveau type de livrable = un fichier, pas de code ».

### 4.4 Réutilisation de missions passées (à cadrer, **phase 2**)
Valeur réelle pour un cabinet : partir d'un ToR **approuvé** d'une mission similaire. Risque : fuite d'informations d'un client vers un autre (contraire à H4). **Décision** : uniquement la **structure** (plan, formulations génériques) des livrables approuvés, après **anonymisation** et accord explicite ; jamais les passages ni les chiffres. Hors périmètre cette nuit ; mentionné dans le rapport comme perspective.

### 4.5 Banc d'attaque (red team) automatisé
Corpus de documents piégés (consignes cachées, fausses citations, chiffres contradictoires) avec **taux de réussite d'attaque** mesuré à chaque version. Démonstration forte pour un jury.

### 4.6 Refus calibré
Mesurer **deux** erreurs : refus manqué (preuves absentes mais texte produit) et faux refus (preuves présentes mais refus). Jeu de test construit en **retirant** volontairement les passages-preuves.

### 4.7 Ce qu'on **n'ajoute pas**
Agents autonomes, appel d'outils par le modèle, recherche web, graphe de connaissances : complexité sans gain mesurable, et surface d'attaque accrue.

## 5. Plan révisé (résumé ; détail en `09`)

| Phase | Contenu révisé | Testable cette nuit ? |
|---|---|---|
| B | Contrats + stockage abstrait + lecture de documents + recherche mixte + corpus synthétique or | Oui (SQLite, FakeProvider) ; Postgres demain |
| C | Gabarits, prompts sécurisés, constats (« preuve d'abord »), génération par section, vérificateur, priorisation, graphe | Oui |
| D | Comptes et rôles, circuit de validation, versions, audit, exports DOCX/PPTX (PDF si LibreOffice), interface Next.js | Oui sauf PDF et Playwright |
| E | Étoile, chargement incrémental, vues, indicateurs, données de démo, export CSV, guide Power BI | Oui (SQLite) ; Power BI demain |
| F | Banc d'évaluation A/B/C/D (simulation), jeu d'entraînement, scripts LoRA sûrs (simulation) | Simulation oui ; réel demain |
| G | Images, installation hors ligne, sauvegarde, guide d'exploitation | Écrit cette nuit, testé demain |

## 6. Critères d'acceptation globaux (proposés, à calibrer avec l'encadrant)

| Mesure | Cible prototype | Où |
|---|---|---|
| Erreurs injectées détectées par le vérificateur (fausse source, source d'un autre dossier, chiffre inventé, fait sans source) | **100 %** | tests C |
| Rappel@10 sur le corpus synthétique or | ≥ 0,90 | tests B |
| Fuite inter-dossiers | **0** passage | tests B |
| Export d'un livrable non approuvé | **impossible** (403) | tests D |
| TPV avec un vrai modèle 2–4 B, configuration B | ≥ 0,80 (**à calibrer**) | éval. F, demain |
| Taux de réussite des attaques d'injection (sortie contenant le jeton canari) | ≤ 5 % (**à calibrer**) | éval. F, demain |

## 7. Trois décisions principales

1. **« Preuve d'abord »** : constats validés → feuille de route → ToR/CdC par initiative.
2. **Stockage via SQLAlchemy Core** : tables uniques, SQLite pour tous les tests de la nuit, PostgreSQL/pgvector écrit et testé demain.
3. **Le TPV comme indicateur central**, mesuré du vérificateur jusqu'à Power BI ; la LoRA est une expérience évaluée, pas une promesse.
