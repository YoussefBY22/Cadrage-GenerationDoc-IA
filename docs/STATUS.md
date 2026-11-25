# STATUS — Phases A à G1 hors ligne (nuit 1), puis passage au réel (nuit 2, 22/11/2026)

> **État au 25/11/2026 (matin).** Détail : `docs/19` §11-12 ; explications : [`20-comprendre-l-apprentissage.md`](20-comprendre-l-apprentissage.md).
>
> | Fait et vérifié (nuit du 24 au 25/11) | Preuve |
> |---|---|
> | PR #20, #21, #22, #19 fusionnées (CI verte) | GitHub |
> | Entraînement v5 (Kaggle, 43 min) testé : équivalent à v4, v4 gardé | docs/19 §11, docs/20 |
> | Axes : imposés par la fiche de contexte, sinon rangés par le sens (74 constats : 6 axes de 9 à 16) | docs/19 §12 |
> | Feuille de route réelle (74 constats) en 24 min, 21 initiatives, aucune partie perdue | docs/19 §12 |
> | Réponses du modèle bornées, phrases répétées retirées, titres recopiés écartés, partie ratée reprise | tests |
> | Captures de l'interface dans Google Drive | « Cadrage IA — captures du 25-11-2026 » |
>
> | Reste à faire, dans l'ordre | |
> |---|---|
> | ~~1. Rattacher les constats orphelins~~ fait le 25/11 (11 → 0, liens marqués à vérifier) | docs/19 §13 |
> | 2. CdC : « proposer quand même » fait (exigences fonctionnelles utilisables) ; reste : exigences saisies par le consultant, document de besoins | code + UI |
> | 3. Chat : consignes qui pilotent la génération (par mois, document prioritaire) | code + UI |
> | 4. Horizons en mois : indicatifs affichés (0-6 / 6-12 / 12-24) ; reste : date de départ et durées réelles | code + UI |
> | 5. Prochain paquet : TdR « objectifs / livrables » appuyés sur les recommandations ; plus de conflits | données |
> | 6. Cache Ollama 8 bits ; tests sur les rapports de Youssef ; recalibrer le filtre de pertinence | mesure |
>
> **État au 24/11/2026 (soir).** Détail : [`19-entrainement-et-tests-reels.md`](19-entrainement-et-tests-reels.md).
>
> | Fait et vérifié (24/11) | Preuve |
> |---|---|
> | Premier entraînement réussi : Qwen3-4B + LoRA (341 exemples publics, 21 min sur Colab T4) | docs/19 §3 |
> | Test sur 169 exemples jamais vus : choix répondre/refuser 114 → 168, extraction 3 → 31 sur 31, position 46 → 50 sur 50 | docs/19 §4 |
> | Banc dans l'application : refus manqués 40 % → 10 %, citations et chiffres 100 % | docs/19 §5 |
> | Import Ollama : gabarit comparé sans l'ordre des paramètres | #20 |
> | Vrai rapport (Cour des comptes UE 17/2022) : position 4/4, conflit 7/8, constats extraits sans échec | docs/19 §6 |
> | Feuille de route par axes : un vrai rapport (55 constats) passe dans 4 096 jetons ; TdR limitées aux constats de l'initiative | #21 |
> | Tâche « axes » dans le jeu d'entraînement (paquet v5, 675 exemples) | #22 |
>
> | Constaté, à traiter | |
> |---|---|
> | Conflit recommandation / stratégie : 11 sur 24 au test (le modèle penche vers « aligné ») | plus d'exemples de vrais conflits |
> | Gravité des constats mal calibrée (presque tout « faible ») ; phrases de méthode prises pour des constats | données d'extraction |
> | Les réponses de la Commission produisent des « constats » | code : réserver ce rôle à la position |
> | Feuille de route : 2 axes seulement, 6 constats sur 55 sans initiative, ~27 min | entraînement v5, puis remesure |
> | TdR « objectifs » refusée alors que les recommandations les donnent | données + gabarit |
> | GPU à 85-91 °C sous charge | repos de 5 min entre passages |
>
> | Reste à faire, dans l'ordre | |
> |---|---|
> | 1. Relire puis fusionner #20 → #21 → #22 (#22 s'appuie sur les deux), puis #19 (documentation) | humain |
> | 2. Entraînement v5 sur Kaggle (carnet de la branche de #22), puis test par tâche dont « axes » | humain + GPU |
> | 3. Remesurer la feuille de route par axes avec le modèle v5 sur le vrai rapport | GPU local |
> | 4. Cache Ollama en 8 bits (fenêtre 8 192 à mémoire égale), mesure sur le banc | réglage |
> | 5. Correctifs : réponses de l'institution hors constats ; rattacher chaque constat à une initiative | code |
> | 6. Horizons en mois (0-6 / 6-12 / 12-24) à partir d'une date de départ et des durées saisies | code + UI |
> | 7. Tester sur des rapports de Youssef ; recalibrer le filtre de pertinence (0,45) | mesure |
> | 8. Studio d'entraînement dans l'application (R27), espace client (R20) : spécifiés, non construits | code |
>
> **État au 23/11/2026.** Les sections ci-dessous décrivent les nuits 1 et 2 ; ce bloc les met à jour.
>
> | Fait et vérifié | Preuve |
> |---|---|
> | Plus de coupe silencieuse de la fenêtre de contexte (Ollama coupait le début des invites au-delà de 4 096 jetons) | #7 |
> | Registre de modèles : choix, test automatique, activation, retour arrière, limites affichées | #11, testé sur Ollama réel |
> | Rôles de documents, priorités institutionnelles, projets existants, 8 contrôles de cohérence | #12 ; réel : 5 initiatives sur 5 reliées à la bonne priorité |
> | Verrou d'approbation : un défaut de preuve ne s'acquitte plus, l'export refuse au lieu d'effacer | #14 |
> | Nombres en lettres et fourchettes contrôlés | #9 |
> | Power BI par acteur, mesures absentes affichées « Non mesuré » | #6 |
> | Cahier des charges v0.2 et architecture cible ; proposition de tableau de bord client | #8, #13 |
> | Référentiels dans les gabarits (étiquette COBIT retirée des consignes après mesure) | #2 |
> | Chaîne d'export de l'entraînement (fusion, GGUF, import Ollama 0.40.17, réponse) | rejouée le 23/11 sur la base |
>
> | Constaté, à traiter | |
> |---|---|
> | Sans porte de pertinence, 70 % de refus manqués ; avec elle 0 % (seuil calibré sur le même corpus) | `lots/R2.md` |
> | 1 attaque par consigne cachée sur 5 suivie par le modèle (signalée, non approuvable) | `lots/R2.md` |
> | Section TdR « Profil » : recopie des constats faute de décision humaine | lot B en cours |
> | GPU à 89-91 °C pendant les mesures | brider tout calcul long |
> | Aucun entraînement abouti ; pilote de 30 exemples relu par l'assistant (pas une validation humaine) | jeu par livrable en cours |


Branche `main` : 19 lots B0 → G1 (nuit 1, faux modèle) puis T1, T2, UI, EN, T4, T6 (nuit 2, réel). Lots Q (PDF) et Q2 (porte de pertinence) terminés ; ce document : lot V, complété par l'orchestrateur. Les sections 1 à 3 décrivent l'état de la nuit 1 ; la section 1 bis résume la nuit 2. Comptes rendus détaillés : `docs/lots/<ID>.md` (index et « Pour comprendre » : `docs/lots/README.md`).

## 1. Fait
Tout le produit existe et passe ses tests **avec un faux modèle** (aucun vrai modèle, aucune base PostgreSQL, aucun Docker n'a tourné).

| Bloc | Lots | Contenu |
|---|---|---|
| Socle | B0, B1 | contrats Pydantic gelés, routeurs découverts, stockage abstrait (SQLite en test, PostgreSQL + pgvector prévu), Alembic |
| Lecture / recherche | B2, B3, B5 | PDF/DOCX/PPTX/TXT, détecteur d'injection, découpage, BM25 + vecteurs + RRF, ingestion, API dossiers/documents/recherche |
| Corpus | B4 | 3 institutions fictives, 60 faits, 27 constats, 30 requêtes, 5 documents piégés |
| Génération | C1, C2, C3, C4 | gabarits FR et prompts à nonce, vérificateur citations/chiffres (8 codes), score + vagues + chemin critique, orchestration « preuve d'abord » |
| Validation / export | D1, D2 | comptes argon2, jetons, quatre yeux, versions, diff, audit ; DOCX, PPTX, PDF (soffice) |
| Interface | D3a, D3b | Next.js 15 : dossiers, documents, recherche, constats, éditeur TipTap ancré, versions, feuille de route |
| Données / BI | E1, E2 | entrepôt en étoile (10 dim., 5 faits, 7 vues, 14 KPI), ETL idempotent, démo (graine 42), CSV, `bi/` (Power BI, Metabase) |
| Évaluation / entraînement | F1, F2 | banc A/B/C/D + bootstrap (mode simulation), jeu d'entraînement et scripts QLoRA sûrs (simulation) |
| Livraison | G1 | compose durci (seul `proxy` sur `edge`), Dockerfiles, paquet hors ligne, sauvegarde/restauration, `docs/10-exploitation.md` |

## 1 bis. Nuit 2 — passage au réel (22/11/2026)
| Lot | Résultat |
|---|---|
| **T1** PostgreSQL | Docker démarré, `pgvector/pgvector:pg16` sur :5433, migrations, HNSW, entrepôt, 7 vues et rôle `bi_reader` **sans bug** ; `pytest -m postgres` : 4 passés ; l'API du compose n'a pas d'accès Internet (vérifié). |
| **T2** Ollama | *Mesures à refaire : invites possiblement tronquées à 4 096 jetons (constat du 22/11).* **qwen3:4b** (Apache 2.0) et **bge-m3** (MIT) sur GTX 1650 4 Go. Évaluation B réduite (1 institution, 31 sections) : latence p50 **18,2 s**, p95 23,1 s, 40 jetons/s, VRAM 3,1 Go ; faux refus 60 → 10 % après `num_gpu=99` (une passe, bruit de ±1–2 sections) ; rappel@10 **1,000**. Le TPV (1,000) ne discrimine pas. |
| **UI** | Refonte « Cadrage » (jaune `#FFE600`, anthracite, Inter, FR/EN), sans logo ni marque ; Playwright e2e vert ; captures dans `docs/img/`. |
| **EN** | Gabarits, prompts, nombres anglais du vérificateur et exports en français et en anglais. |
| **T4** | **103 documents CC BY** (Banque mondiale, Commission européenne), 82 EN / 21 FR ; 3 105 exemples d'entraînement (jeu **rejeté** le 22/11/2026 après lecture : réponses presque toutes recopiées des passages (2 061 sur 2 067), questions faites de mots-clés, 83 % en anglais, aucune feuille de route ni TdR ni cahier des charges) ; 34 questions de test rédigées par une IA, non relues par un humain ; Kaggle non utilisé (compte exigé). |
| **T6** | Thème Power BI EY, projet PBIP (5 pages, **non ouvert dans Desktop**), CSV de démo, LibreOffice installé, test `-m soffice` vert, hypothèses H1 à H7 au §13 du cahier des charges. |
| **Q** | Export PDF réparé (soffice détecté dans Program Files, profil et cwd temporaires contre l'accès contrôlé aux dossiers de Defender), `-m soffice` vert. Trois itérations de prompt : toutes **rejetées** (faux refus 0 % mais refus manqués 30 à 50 %). |
| **Q2** | **Porte de pertinence** avant l'appel au modèle (`app/generation/relevance.py`, meilleur cosinus bge-m3 < 0,45 → refus sans appel) + prompts de l'itération 1 : refus 32 %, **faux refus 0 %, refus manqués 0 %** sur une passe réelle (31 sections), **à remesurer** (invites possiblement tronquées). Réserve : seuil calibré sur ce même échantillon synthétique, marge de 0,019 ; à recalibrer sur le jeu or réel (T4) via `RELEVANCE_THRESHOLD`. 436 tests verts. |

Contrôles de l'orchestrateur après fusion : backend **432 passés, 5 sautés** ; PostgreSQL réel 4 passés ; entraînement 33 ; interface : lint, 22 tests, build. Le test `soffice` reste sauté sans `soffice` dans le PATH (lot Q).

**Toujours simulé ou à faire** : entraînement LoRA (T5), modèle C ; chiffres du banc sur corpus fictif ; valeurs du tableau de bord ; PBIP à ouvrir dans Power BI Desktop ; B complète (≈ 1 h) ; peu de français dans le corpus (17 %).

## 2. Testé (exécuté pour R2, branche `integration`)
```
cd backend && .venv\Scripts\ruff check .            -> All checks passed!
cd backend && .venv\Scripts\pytest -q                -> 388 passed, 2 skipped (Postgres, LibreOffice)
cd backend && .venv\Scripts\python -m pytest ..\training\tests -q -> 22 passed
Front (D3b) : npm run lint (0 erreur) · npm test (22 tests) · npm run build (réussi) — mesurés par le lot, non relancés pour R2
docker compose config -q (avec/sans --profile llm) : OK (G1)
```
Progression des tests : phase A 22 → B0 46 → B4 55 → B1 63 → B3 69 → B2 103 → B5 166 → C1 170 → C2 209 → C4 269 → D1 296 → E1 277 (branche isolée) → D2 265 (idem) → D3b 361 → G1 388 (intégration).

**Chiffres mesurés (corpus synthétique, faux modèle : valident la mécanique, pas un modèle)**
| Mesure | Résultat | Lot |
|---|---|---|
| Rappel@10 (30 requêtes, 3 dossiers, tous formats) | **1,000 (30/30)**, seuil 0,90 | B5 |
| Injections détectées / faux positifs | 14 attaques détectées ; 0 faux positif sur 25 phrases | B2 |
| Erreurs injectées détectées (8 codes, ≥ 3 par code) | 23/23 cas construits (hors nombres en lettres, fourchettes et sens) ; 20 phrases correctes → 0 bloquant | C2 |
| Extraction de nombres | 40 cas FR/EN | C2 |
| TPV simulé du banc (taux d'erreur 30 %, 189 sections) | **0,847**, IC95 [0,815 ; 0,877] ; MRR 0,73 ; rappel@10 1,00 ; 4,6 s | F1 |
| TPV de la démo BI (valeurs inventées) | C 0,86 > B 0,82 > D 0,78 > A 0,35 | E2 |
| Jeu de démo (graine 42) | 12 dossiers, 36 documents, 144 passages, 109 runs, ~2 470 lignes d'entrepôt | E2 |
| e2e corpus → constats → feuille de route → ToR | ToR 6 sections, TPV 1, 1,4 s | C4 |

## 3. Pas encore fait / limites
- **Rien n'a tourné avec un vrai modèle, PostgreSQL, Docker, un navigateur, LibreOffice, Power BI** : tous les chiffres ci-dessus viennent du faux modèle. Chemins non exécutés : `PgVectorSearch`/HNSW/JSONB (B1), schéma `dw`, `roles.sql`, vues sur Postgres (E1), exports PDF (D2), builds et scripts `.sh`/`.ps1` (G1), `OllamaProvider`, `TorchBackend` et conversion GGUF (F2), mesures DAX / relations Power BI (E2).
- **Vérificateur** : prouve l'ancrage, pas la vérité ; nombres en lettres non gérés (C2). Les constats et la feuille de route du banc ne sont mesurés que sur 1 graine / 1 institution (F1).
- **Écarts aux contrats de `06`** (aucun bloquant) : méthodes de lecture hors `Repository` (documents, chunks, livrables, versions, audit, exports) lues via `repo.engine` + `storage.schema` (B5, C4, D1, D2) ; routes ajoutées `…/acknowledgements`, `…/comments` (D1) ; réponses 401 au format `detail` (D1) ; contexte d'initiative d'un ToR conservé dans `DeliverableContent.roadmap` (C4) ; `score_with_warnings` en plus de `score` (C3) ; `0001_initial` appelle `create_all` (B1) ; `dim_client.client_ref` et colonnes de `fact_review` ajoutées (E1) ; Ollama de l'hôte injoignable depuis `internal` (G1).
- **Comptes** : aucune route de création ni de réinitialisation ; script d'administration à fournir (D1, G1). Défaut `auth_mode="token"`.
- **Chiffres des hypothèses** : `baseline_minutes` = 30 min par section (E1) ; licences et tags d'images Docker écrits de mémoire (B2, G1).
- **Demandes non traitées (à intégrer, hors propriété des lots)** :
  - `Repository` : `list_documents`, `get_document`, `get_chunk`, `get_deliverable`, `list_deliverables`, `delete_finding`, `record_export`, `get_deliverable_state`, sessions (B1 ← B5, C4, D1, D2).
  - `config.py` : `dw_pseudonymize` (E1) ; préfixes d'embedding `passage`/`query` (B5) ; gestionnaire d'erreurs global `{"error": …}` ; CORS si origines différentes (D3a).
  - `pyproject.toml` : `package-data` pour `generation/templates` et `export/reference` (C1, D2, B0/G1) ; `eval` hors `packages.find` (B4).
  - `.gitattributes` `*.sh text eol=lf` (G1) ; tests `training/` dans le CI/`testpaths` (F2, partiellement fait par G1).
  - B3 : départage stable des égalités de score (F1) et préfixe `query:` des requêtes (B5).
  - Backend : `alerts` par document ; `GET /templates/{type}` ; déclarer 3 paquets TipTap ; valider l'`include` de `vitest.config.ts` modifié par D3b.
- Dépendances de lecture : pypdf, python-docx, python-pptx, reportlab, argon2 : licences « à vérifier » (`docs/LICENCES-LOGICIELS.md`).

## 4. Décisions (nuit 2 : prises) et à prendre
**Prises** : modèles **qwen3:4b** et **bge-m3** (T2) ; corpus public sous licence ouverte accepté, Kaggle laissé de côté (T4) ; français **et** anglais (EN) ; hypothèses H1 à H7 retenues, à valider avec l'entreprise (`docs/01` §13) ; interface inspirée d'EY sans logo ni nom ; fusions directes sur `main` après les tests.

**À prendre** :
1. **Hypothèse « temps gagné »** : 30 min par section est-elle réaliste ? (E1, H7)
2. **Comptes de production** : script d'administration (`scripts/create_user.py`) ou route protégée ? (D1, G1)
3. **T5** : budget d'entraînement (Colab ou PC la nuit) et règle de décision C contre B (`08` §6).
4. **Français** : ouvrir une source francophone ouverte (AFD, BAD, journal officiel) pour dépasser 17 % du corpus (T4).
5. **Accès contrôlé aux dossiers** (Windows Defender) : autoriser `soffice.bin` si l'export PDF doit écrire hors des dossiers temporaires.
6. **Intégration des demandes** du §3 (Repository, config, package-data) : lot de consolidation.

## 5. Prochaine étape
**Faits (nuit 2) : T1, T2, T4, T6 ; T3 couvert par le test Playwright du lot UI.** Reste **T5** (entraînement LoRA réel, éval C contre B), puis la B complète et l'ouverture du PBIP dans Power BI Desktop. Le tableau ci-dessous garde les commandes d'origine ; les lignes T1, T2, T3, T4 et T6 sont réalisées (voir `docs/lots/`).

Ordre conseillé d'origine : T1 → T2 → T3/T6 → T4 → T5. Commandes à adapter au PC (PowerShell, depuis la racine du dépôt) ; `<…>` à remplir.

| Lot | Objectif | Commandes |
|---|---|---|
| **T1** | PostgreSQL, pgvector, migrations, entrepôt | `docker run -d --name pgt -e POSTGRES_PASSWORD=test -e POSTGRES_DB=cadrage_test -p 127.0.0.1:5433:5432 pgvector/pgvector:pg16` (tag à vérifier ; la base du compose est sur un réseau interne sans port publié) ; `$env:TEST_POSTGRES_URL="postgresql+psycopg://postgres:test@127.0.0.1:5433/cadrage_test"` ; `cd backend` ; `.venv\Scripts\alembic upgrade head` ; `.venv\Scripts\pytest -q -m postgres` ; rôle `bi_reader` : `db/dw/roles.sql` (changer `CHANGER_MOI`) |
| **T2** | Licences, Ollama, première éval B | vérifier `08` §8 ; `ollama pull <modèle>` (génération et embeddings) ; renseigner `.env` (`LLM_PROVIDER=ollama`, `OLLAMA_*`) ; test de fumée `OllamaProvider` ; remplir `*_REMPLIR_T2` dans `backend/eval/configs/B.yaml` ; `cd backend` ; `.venv\Scripts\python -m eval.harness.run --config eval/configs/B.yaml` |
| **T3** | Parcours navigateur (Playwright) | `cd frontend` ; `npm install` ; `npm run build` ; `npx playwright install chromium` ; parcours : import → constats → ToR → approbation → export (à écrire avec toi) |
| **T4** | Corpus public et jeu d'entraînement | télécharger les documents, noter chaque licence dans `data/LICENCES.md` ; `cd backend` ; `.venv\Scripts\python -m training.dataset.build` (options : voir `training/README.md`) |
| **T5** | Entraînement LoRA réel, éval C vs B | `pip install -r training/requirements-train.txt` ; essai 1 % puis `python -m training.train_lora --budget-hours <h>` (profil `colab` ou `pc-nuit`, voir `training/README.md`) ; export GGUF ; `python -m eval.harness.run --config eval/configs/C.yaml` ; règle de décision de `08` §6 |
| **T6** | LibreOffice, Power BI, images Docker | `.venv\Scripts\pytest -q -m soffice` (LibreOffice installé) ; `docker compose build` ; `docker compose up -d` ; `python -m app.dw.demo --seed 42` puis `python -m app.dw.export_csv --out bi/export/` ; suivre `bi/README.md` (5 pages) ; `deploy/offline/build_bundle.ps1` |

Avant T1, vérifier chaque commande dans le README du lot concerné : plusieurs options (`--out`, graines, profils) n'ont pas été exécutées sur la machine cible.
