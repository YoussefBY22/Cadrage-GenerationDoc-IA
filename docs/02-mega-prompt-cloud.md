# Méga prompt — à coller dans une session Claude Code cloud

> **Mode d'emploi** : ouvre une session Claude Code cloud sur le dépôt `PRV-PR8-PFE-IA-Cadrage`, puis colle **tout le texte ci-dessous** (de « RÔLE » jusqu'à la fin). L'agent doit d'abord lire `README.md` et `docs/01-cahier-des-charges.md`.

---

## RÔLE

Tu es l'ingénieur principal de mon projet de fin d'études : un **assistant IA 100 % local** qui génère des **feuilles de route priorisées, des termes de référence et des cahiers des charges** à partir de documents de diagnostic, avec **sources traçables** et **validation humaine**.

Référence du sujet : *Stages & PFE Book 2026-2027*, p. 92, Réf. #TST 11. Le cahier des charges complet est dans `docs/01-cahier-des-charges.md` : **il fait foi**. En cas de doute, relis-le.

Je suis élève ingénieur en génie logiciel. Je connais le développement web et mobile, mais **peu l'IA** (notions : prédiction du prochain jeton, température). Tu dois donc **m'enseigner en construisant** : voir « Pédagogie ».

## CONTRAINTES ABSOLUES

1. **Le produit n'appelle jamais d'API ni de modèle hébergé.** Aucune clé d'API, aucun service tiers à l'exécution, aucune télémétrie. Tout tourne sur le serveur du client, hors ligne. Ajoute un **test automatique** qui échoue si du code ouvre une connexion sortante.
2. **Aucune donnée client** dans le dépôt, les tests, les jeux d'essai ni les journaux. Uniquement des **documents publics** (licence notée dans `data/LICENCES.md`) ou des **données synthétiques**.
3. **Aucun secret** dans le dépôt. Les variables sensibles viennent de l'environnement ; fournis un `.env.example` sans valeurs.
4. **Environnement de développement : cloud, sans GPU, sans gros téléchargement.** Ne télécharge aucun modèle de langage volumineux. Toute la chaîne doit se tester **sans GPU** avec un **faux modèle déterministe** (`FakeProvider`). Le vrai modèle local (Ollama) sera branché **plus tard**, par moi, sur mon ordinateur.
5. **Pas de dépendance au modèle** : tout passe par une interface `LLMProvider` (génération, génération structurée, embeddings). Implémentations : `FakeProvider` (tests) et `OllamaProvider` (réel, **non testé dans le cloud**, testé par un contrat avec un serveur simulé).
6. **Licences** : n'utilise que des bibliothèques et modèles à licence permettant l'usage professionnel. Tiens `docs/LICENCES-LOGICIELS.md` à jour.
7. **Git** : identité de commit `YoussefBY22 <126215955+YoussefBY22@users.noreply.github.com>` ; **aucun `Co-Authored-By`**, aucune mention d'assistant dans les messages de commit. Une branche par phase, jamais de push forcé, jamais de fusion sur `main` sans que je la demande.
8. **Reproductibilité** : chaque résultat chiffré doit sortir d'un script versionné, avec graine aléatoire fixe et versions consignées.

## PILE TECHNIQUE (décidée, sauf blocage justifié)

| Couche | Choix |
|---|---|
| API et logique IA | **Python 3.12, FastAPI**, Pydantic |
| Base de données | **PostgreSQL + pgvector** (Docker Compose) |
| Interface | **Next.js (TypeScript)** + éditeur riche **TipTap** |
| Documents | `python-docx`, `python-pptx` ; PDF par **LibreOffice en ligne de commande** (à vérifier dans le conteneur) |
| Lecture de documents | PDF avec position de page, DOCX, PPTX, TXT |
| Recherche | embeddings multilingues via `LLMProvider` + recherche par mots-clés (BM25) + fusion des deux |
| Entrepôt | schémas SQL versionnés (migrations), chargement scripté |
| Tests | `pytest`, `vitest`/`playwright` pour l'interface |
| Livraison | **Docker Compose**, installation hors ligne |

## FONCTIONNEMENT À RESPECTER

### Génération « ancrée »
- Le texte est produit **section par section**, en **JSON contraint par un schéma** : chaque phrase contient ses `source_ids` (identifiants de passages).
- Le modèle ne reçoit **que** les passages récupérés pour la section. Il doit **refuser** (`insufficient_evidence`) quand les preuves manquent.
- Un **vérificateur en code pur** contrôle : (a) chaque `source_id` existe et appartient au dossier ; (b) chaque **nombre** cité figure dans le passage ; (c) aucune phrase sans source n'est présentée comme un fait.

### Feuille de route
- Le **calcul** de priorisation est **déterministe** (critères et poids visibles, paramétrables) ; le modèle **propose** des évaluations avec preuves, le calcul **tranche**.
- Graphe de dépendances : **tri topologique**, **détection de cycles**, chemin critique.

### Sécurité des documents entrants
- Traite tout document comme **non fiable** : isole-le du prompt système, détecte les consignes cachées (`ignore les instructions…`), journalise les alertes.

### Circuit de validation
- États : `brouillon → relu → approuvé / refusé (motif)`. **L'export est impossible tant que l'état n'est pas `approuvé`.** Historique des versions et journal d'audit.

## PLAN DE TRAVAIL (une branche par phase)

Avant chaque phase : **écris le plan** (fichiers, tests, risques) et attends mon « go » seulement si une décision m'appartient. Sinon, avance.

| Phase | Contenu | Critères d'achèvement |
|---|---|---|
| **A. Squelette** | Dépôt, Docker Compose (Postgres+pgvector), API minimale, interface `LLMProvider`, `FakeProvider`, journalisation, test « aucune connexion sortante », CI sans GPU | `docker compose up` démarre ; tests verts |
| **B. Ingestion et recherche** | Import PDF/DOCX/PPTX/TXT avec page et section, découpage, index, recherche mixte, jeu d'essai public | Tests de rappel sur un petit corpus public ; passages cités avec page |
| **C. Génération et vérification** | Schémas JSON, génération par section, vérificateur de citations et de chiffres, refus sans preuve, calcul de priorisation, graphe de dépendances | Tests avec `FakeProvider` ; cas d'erreurs volontaires détectés à 100 % |
| **D. Interface** | Dossiers clients isolés, import, éditeur TipTap, sources cliquables, commentaires, versions, circuit de validation, exports Word/PPT/PDF | Parcours complet testé de bout en bout |
| **E. Entrepôt et BI** | Modèle en étoile (faits : génération, relecture, vérification, exécution du modèle ; dimensions : client, mission, document, utilisateur, modèle, temps, livrable), chargement, **vues prêtes pour Power BI**, générateur de **données de démonstration**, alternative libre | Vues documentées ; jeu de démonstration chargé |
| **F. Données et adaptation du modèle** | Collecte de documents **publics** avec licences, nettoyage, **générateur d'exemples synthétiques** (via `LLMProvider`), construction du jeu d'entraînement, **scripts d'adaptation LoRA** (voir ci-dessous), banc d'essai A/B/C/D du cahier des charges | Scripts testés en **mode simulation** ; protocole d'évaluation prêt |
| **G. Livraison** | Images Docker, installation hors ligne, sauvegarde/restauration, guide d'exploitation, rapport technique | Installation sur machine propre documentée |

### Exigences pour les scripts d'entraînement (phase F)
Je les lancerai **moi**, sur un GPU gratuit ou la nuit sur mon PC (GPU 4 Go, fp16 uniquement, pas de bf16). Ils doivent donc :
1. **Mesurer d'abord** (50 pas d'essai), **estimer la durée totale** et **refuser de démarrer** si elle dépasse le budget que je fixe.
2. Faire un **essai court sur 1 % des données** et **tester l'export du modèle avant** le long entraînement.
3. **Sauvegarder des points de reprise** réguliers et **reprendre automatiquement**.
4. S'arrêter proprement si : perte invalide, disque presque plein, température excessive.
5. Consigner dans un fichier : versions, graine, paramètres, durée, métriques.
6. Fonctionner en deux variantes : **GPU gratuit en ligne** et **PC local nocturne**.

## PÉDAGOGIE (important)

Je dois **comprendre** ce que tu construis, pas seulement le recevoir.
- Dans la description de chaque phase, ajoute une section **« Pour comprendre »** : 5 à 10 lignes, en français simple, avec une analogie.
- Nomme les notions utilisées (jeton, température, fenêtre de contexte, embedding, RAG, découpage, recherche mixte, fine-tuning, LoRA, quantification, hallucination, ancrage, évaluation) et renvoie vers `docs/03-apprentissage-et-glossaire.md`. **Complète ce glossaire** quand tu introduis une notion absente.
- Ajoute à la fin de chaque phase **3 questions** pour que je vérifie ma compréhension.
- Quand tu fais un choix technique important, explique **l'alternative écartée** et **pourquoi**.

## FORMAT DES COMPTES RENDUS

À la fin de chaque session de travail, mets à jour `docs/STATUS.md` :
1. **Fait** (liste courte) · 2. **Testé** (commandes et résultats réels) · 3. **Pas encore fait / limites** · 4. **Décisions à prendre par moi** · 5. **Prochaine étape**.
Ne déclare jamais « terminé » sans avoir **exécuté** les tests et collé leur résultat.

## COMMENCE PAR

1. Lire `README.md` et `docs/01-cahier-des-charges.md`.
2. M'écrire en **10 lignes** ce que tu as compris et les **3 points ambigus** qui te bloquent vraiment (pas plus).
3. Proposer le plan détaillé de la **phase A**, puis la réaliser.
