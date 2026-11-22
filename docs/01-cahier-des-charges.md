# Cahier des charges — Assistant IA local de cadrage

**Projet de fin d'études** · Version 0.1 · 21/11/2026 · Auteur : Youssef Ben Youssef
**Référence du sujet** : *Stages & PFE Book 2026-2027*, page 92, **Réf. #TST 11** — « Conception d'un outil IA de génération de feuilles de route, de termes de référence et de cahiers des charges » (diplôme : ingénieur ; 1 poste ; durée : 6 mois).

---

## 1. Contexte

D'après le sujet :

- Une **feuille de route** doit rapprocher les **constats d'un diagnostic**, les **priorités institutionnelles** et les **dépendances entre projets**.
- La préparation des **termes de référence** et des **cahiers des charges** demande ensuite de **reformuler** ces éléments dans des **documents cohérents et adaptés au contexte**.
- Ce travail mobilise **de nombreuses sources** et comporte des **tâches de rédaction répétitives**.
- L'IA générative peut produire une **première version**, **à condition que les sources soient traçables** et que **le consultant reste responsable de la validation**.

## 2. Objectif (tel que posé par le sujet)

Développer un **assistant** qui transforme les **documents fournis** en :

1. une **proposition de feuille de route priorisée** ;
2. des **termes de référence** adaptés au contexte ;
3. un **cahier des charges** adapté au contexte.

Le prototype doit **rendre visibles les sources utilisées** et **intégrer une étape de révision humaine** avant utilisation des livrables.

## 3. Choix de conception ajoutés par ce projet

Ces points **ne figurent pas dans le sujet**. Ce sont des choix de travail (D1 à D5) ; les hypothèses à valider avec l'entreprise sont au §13 (H1 à H7).

| # | Choix | Justification |
|---|---|---|
| D1 | **Aucun appel à une API ou un modèle hébergé** pendant l'utilisation du produit | Les documents de diagnostic sont confidentiels. |
| D2 | Modèle de langage **ouvert, exécuté sur le serveur du client** | Même raison ; le client garde le contrôle. |
| D3 | Le modèle est **adapté** (fine-tuning léger) pour **rédiger et structurer** les livrables | Qualité et cohérence de forme. |
| D4 | Les **connaissances du client** restent dans une base interrogée à la demande (**RAG**), jamais dans les poids du modèle | Confidentialité, mise à jour, traçabilité. |
| D5 | Un **tableau de bord** (Power BI ou équivalent sur site) mesure l'usage et la qualité | Les utilisateurs connaissent Power BI. |

## 4. Périmètre

**Inclus (prototype)** : ingestion de documents, recherche dans ces documents, génération des trois livrables avec citations, vérification automatique des sources et des chiffres, interface de relecture et d'édition, exports Word / PowerPoint / PDF, entrepôt de données et tableau de bord, jeux de données publics pour l'adaptation du modèle, banc d'essai d'évaluation, livraison par conteneurs sur serveur isolé.

**Exclu (à ce stade)** : accès à de vrais documents clients ; entraînement sur le serveur du client (prévu **après** l'obtention de l'accès) ; authentification d'entreprise (SSO) ; application mobile ; multilingue au-delà du français et de l'anglais.

## 5. Contraintes

- **C1 Confidentialité** : zéro flux sortant vers un service externe à l'exécution ; aucune clé d'API ; aucune télémétrie.
- **C2 Licences** : modèles et bibliothèques sous licences permettant l'usage professionnel (vérifier chaque fiche de modèle).
- **C3 Matériel de développement** : GPU de 4 Go, 16 Go de RAM → modèles de petite taille en local ; l'adaptation du modèle se fait sur des données **publiques ou synthétiques** uniquement (GPU gratuit en ligne ou PC en nuit).
- **C4 Reproductibilité** : chaque résultat chiffré doit pouvoir être refait par script.
- **C5 Livraison** : déploiement hors ligne par conteneurs (Docker Compose).

## 6. Utilisateurs et rôles

| Rôle | Besoin |
|---|---|
| **Consultant** (utilisateur principal) | Déposer des documents, obtenir un premier jet, vérifier les sources, corriger, valider, exporter. |
| **Relecteur / manager** | Approuver ou refuser avec motif ; voir l'historique. |
| **Administrateur** | Gérer les comptes, les dossiers clients, les modèles et les sauvegardes. |
| **Décideur** | Consulter le tableau de bord (usage, qualité, temps gagné). |

## 7. Exigences fonctionnelles

| ID | Exigence | Lien avec le sujet |
|---|---|---|
| FR-01 | Créer un **dossier** par client/mission, isolé des autres. | Confidentialité (H1) |
| FR-02 | Importer des documents (PDF, Word, PowerPoint, texte) et conserver **page et section** de chaque passage. | « Documents fournis » ; sources traçables |
| FR-03 | Découper les documents en passages numérotés et les indexer (recherche **par sens et par mots-clés**). | « Nombreuses sources » |
| FR-04 | Générer une **feuille de route priorisée** : initiatives, priorités, **dépendances**, calendrier proposé. | Objectif 1 |
| FR-05 | Générer des **termes de référence** adaptés au contexte (contexte, objectifs, livrables, planning, compétences, critères). | Objectif 2 |
| FR-06 | Générer un **cahier des charges** (périmètre, exigences, contraintes, recette). | Objectif 3 |
| FR-07 | Chaque affirmation porte une **citation** vers un passage précis ; l'utilisateur ouvre la source en un clic. | « Sources utilisées visibles » |
| FR-08 | **Vérificateur automatique** : toute citation doit exister ; tout chiffre cité doit se retrouver dans la source ; sinon la phrase est signalée. | Sources traçables |
| FR-09 | La **priorisation** repose sur un calcul explicite et reproductible (critères et poids visibles) ; le modèle propose, le calcul tranche. | Priorités et dépendances |
| FR-10 | **Détection de cycles** et d'incohérences dans les dépendances entre projets. | Dépendances entre projets |
| FR-11 | Le modèle **refuse** de produire une section si les sources sont insuffisantes et le dit. | Sources traçables |
| FR-12 | **Éditeur de texte** intégré : modifier, commenter, comparer les versions, restaurer. | Tâches de rédaction |
| FR-13 | **Circuit de validation** : brouillon → relu → approuvé / refusé (avec motif) ; export bloqué tant que non approuvé. | « Étape de révision humaine » |
| FR-14 | **Exports** Word, PowerPoint et PDF avec la mise en forme du modèle de document choisi, **sans avoir besoin de Word** pour travailler. | Livrables |
| FR-15 | **Modèles de documents** paramétrables (trames, plan type, charte). | Adaptés au contexte |
| FR-16 | **Journal d'audit** : qui a fait quoi, avec quelle version du modèle et quelles sources. | Responsabilité du consultant |
| FR-17 | **Entrepôt de données** alimenté automatiquement (modèle en étoile) et **tableau de bord** (voir §10). | H5 |
| FR-18 | **Banc d'essai** intégré pour comparer des modèles et des réglages (voir §11). | Qualité |

## 8. Exigences non fonctionnelles

- **NFR-01 Confidentialité** : aucune requête sortante ; vérifiée par un test réseau automatique.
- **NFR-02 Sécurité** : comptes et rôles, chiffrement des données au repos, isolation entre dossiers clients, protection contre les consignes cachées dans les documents (*prompt injection*).
- **NFR-03 Performance** : génération d'une section en un temps acceptable sur serveur de client standard ; mesure et publication de la latence.
- **NFR-04 Interchangeabilité du modèle** : le code ne dépend pas d'un modèle précis (interface commune).
- **NFR-05 Testabilité** : toute la chaîne se teste **sans GPU** grâce à un faux modèle déterministe.
- **NFR-06 Exploitabilité** : installation en une commande, sauvegarde/restauration documentées.
- **NFR-07 Traçabilité** : versions du modèle, des données d'entraînement et des paramètres consignées pour chaque livrable.

## 9. Architecture cible (résumé)

- **Interface web** : Next.js, éditeur riche (TipTap), appels vers l'API.
- **API et logique IA** : Python (FastAPI).
- **Modèle** : service local (Ollama ou llama.cpp) derrière une interface `LLMProvider`.
- **Recherche** : embeddings multilingues locaux + **PostgreSQL / pgvector** + recherche par mots-clés.
- **Génération structurée** : sorties contraintes par schéma JSON ; chaque phrase référence ses passages sources.
- **Documents** : Word et PowerPoint générés par code ; PDF par conversion locale.
- **Entrepôt** : schémas transactionnel et analytique dans PostgreSQL ; traitements de chargement scriptés.
- **BI** : vues analytiques consommables par Power BI ; solution libre de secours.
- **Livraison** : Docker Compose, fonctionnement hors ligne.

## 10. Entrepôt de données et tableau de bord

**Faits** : génération de section, relecture, vérification de citation, exécution du modèle.
**Dimensions** : client, mission, document, utilisateur, modèle (version), temps, type de livrable.
**Indicateurs** : taux de sections acceptées sans modification, **distance d'édition** (combien le consultant a réécrit), citations valides, chiffres fidèles, refus pour sources insuffisantes, temps gagné estimé, latence, comparaison entre versions du modèle.

> **Point de vigilance** : *Power BI Service* est hébergé par Microsoft. Pour respecter C1, utiliser *Power BI Desktop* ou *Power BI Report Server* sur site (licence à vérifier), avec une solution libre (par exemple Metabase) en secours.

## 11. Adaptation du modèle et évaluation

**Ce que l'adaptation doit apprendre** : le **format** des trois livrables, le **ton professionnel**, **citer ses sources**, **refuser sans preuve**. Elle n'apprend **pas** de faits sur les clients.

**Données** : documents **publics** de type termes de référence, cahiers des charges et feuilles de route (bailleurs, institutions, marchés publics) avec **licence tracée** ; exemples **synthétiques** produits par un modèle local ; aucun document client.

**Plan d'expériences (ablation)** :

| Configuration | Rôle |
|---|---|
| A. Modèle seul | Référence basse |
| B. Modèle + RAG | Référence principale |
| C. Modèle + RAG + adaptation | Mesure du gain réel |
| D. Variante de taille de modèle | Compromis qualité / vitesse / mémoire |

**Métriques** : validité des citations, fidélité des chiffres, respect de la structure (schéma), couverture des constats du diagnostic, cohérence des dépendances, **évaluation humaine** par grille (clarté, exactitude, utilité), latence.

**Critères d'acceptation (à calibrer après les premières mesures)** : 100 % des chiffres cités vérifiés ou signalés ; citations valides au-dessus d'un seuil fixé avec l'encadrant ; la configuration C n'est retenue que si elle **bat B** sur les métriques de qualité.

## 12. Livrables et jalons

| Jalon | Contenu |
|---|---|
| **J0** | Cahier des charges validé, dépôt, environnement de développement |
| **J1** | Chaîne RAG de bout en bout avec faux modèle, vérificateur, tests |
| **J2** | Interface : éditeur, circuit de validation, exports |
| **J3** | Entrepôt, vues analytiques, tableau de bord |
| **J4** | Jeux de données publics, scripts d'adaptation, premières expériences |
| **J5** | Banc d'essai, résultats comparés, déploiement sur conteneurs |
| **J6** | Version sur le serveur de l'entreprise : modèle plus grand, adaptation réelle, rapport final |

## 13. Hypothèses retenues (à valider avec l'entreprise)

Faute de réponses de l'entreprise à ce stade, le projet retient les hypothèses suivantes. Ce sont des **hypothèses de travail**, pas des faits établis : chacune est à **confirmer ou à corriger** avec l'entreprise, et sa révision peut modifier le périmètre ou les mesures.

| N° | Hypothèse retenue | Ce qui change si elle est fausse |
|---|---|---|
| H1 | Le traitement reste **100 % sur site** : aucun document ni aucune requête ne quitte le réseau de l'entreprise (ni cloud public, ni cloud privé). | Un cloud privé accepté élargirait le choix de modèles ; il faudrait revoir le garde-fou de réseau. |
| H2 | **Serveur GPU de 24 Go** de mémoire vidéo en cible ; **PC de démonstration avec 4 Go**, donc un petit modèle quantifié. | Moins de mémoire : modèle plus petit, qualité plus faible. Plus de mémoire : modèle plus gros à évaluer. |
| H3 | Documents en entrée : **PDF, DOCX et PPTX**, en **français et en anglais**, de **10 à 200 pages**. | D'autres formats (scans, tableurs) ou des volumes plus grands demandent de l'extraction et un indexage supplémentaires. |
| H4 | Les livrables suivent des **trames génériques de bailleurs de fonds** ; les trames et chartes internes de l'entreprise ne sont pas connues. | Des trames internes imposeraient de nouveaux gabarits et une validation de leur structure. |
| H5 | Le corpus de développement et d'évaluation est **public (réel) et synthétique** ; **aucune donnée client** n'est utilisée. | Des exemples anonymisés fournis par l'entreprise amélioreraient l'évaluation, sous accord écrit. |
| H6 | Circuit de relecture : le **consultant rédige**, le **manager approuve**, et ce sont **deux personnes distinctes**. | Un autre circuit (relecteur supplémentaire, auto-approbation) modifie les rôles et l'entonnoir de validation. |
| H7 | Critère de réussite du prototype : **0 citation inventée**, **au moins 50 %** des phrases générées **réutilisables telles quelles**, et **au moins 30 %** de **temps gagné** sur la rédaction. | Des seuils différents modifient la lecture des résultats d'évaluation ; le temps gagné reste une **estimation**, non une mesure. |

## 14. Risques

| Risque | Parade |
|---|---|
| Petits modèles qui inventent | Vérificateur, refus sans preuve, relecture humaine |
| Pas de jeu de données public suffisant | Données synthétiques + sélection manuelle, traçabilité des licences |
| Adaptation sans gain | Ablation prévue : on garde la meilleure configuration, sans enjeu d'ego |
| Matériel insuffisant | Interface de modèle interchangeable ; GPU gratuit pour les entraînements publics |
| Périmètre trop large | Jalons ; entrepôt et BI après le cœur RAG + vérification |
| Licences de modèles | Vérification avant chaque choix ; registre des licences |
| Perte d'un entraînement long | Points de sauvegarde, reprise, essais courts, mesure du temps avant lancement |

## 15. Traçabilité : sujet → exigences

| Élément du sujet | Exigences |
|---|---|
| Documents fournis en entrée | FR-01, FR-02, FR-03 |
| Feuille de route priorisée | FR-04, FR-09, FR-10 |
| Termes de référence | FR-05, FR-15 |
| Cahier des charges | FR-06, FR-15 |
| Adaptés au contexte | FR-03, FR-15 |
| Sources visibles et traçables | FR-07, FR-08, FR-11, FR-16 |
| Révision humaine avant utilisation | FR-12, FR-13 |
| Tâches de rédaction répétitives | FR-12, FR-14, FR-15 |
