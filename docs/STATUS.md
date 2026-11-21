# STATUS — Phases A à G1 construites hors ligne (22/11/2026)

Branche d'intégration : `integration` (19 lots B0 → G1 fusionnés) ; ce document : lot R2. Comptes rendus détaillés : `docs/lots/<ID>.md` (index et « Pour comprendre » : `docs/lots/README.md`).

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
| Erreurs injectées détectées (8 codes, ≥ 3 par code) | **23/23 (100 %)** ; 20 phrases correctes → 0 bloquant | C2 |
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

## 4. Décisions à prendre par moi
1. **Modèles** (T2) : quels modèles de génération et d'embeddings installer (budget 4 Go VRAM) ? Valider les licences de `08` §8.
2. **Hypothèse « temps gagné »** : 30 min par section est-elle réaliste ? (E1)
3. **Comptes de production** : veux-tu un script d'administration (premier compte) ou une route protégée ? (D1, G1)
4. **Corpus public** : OK pour télécharger quelques documents de bailleurs sous licence ouverte (T4) ou rester 100 % synthétique ?
5. **Langue** : français seul (gabarit `en/` vide) ou anglais dès maintenant ?
6. **Intégration des demandes** du §3 : un lot de consolidation (Repository, config, package-data) avant T1 ?

## 5. Prochaine étape — lots « avec l'utilisateur » (réseau ou Docker)
Ordre conseillé : T1 → T2 → T3/T6 → T4 → T5. Commandes à adapter au PC (PowerShell, depuis la racine du dépôt) ; `<…>` à remplir.

| Lot | Objectif | Commandes |
|---|---|---|
| **T1** | PostgreSQL, pgvector, migrations, entrepôt | `docker run -d --name pgt -e POSTGRES_PASSWORD=test -e POSTGRES_DB=cadrage_test -p 127.0.0.1:5433:5432 pgvector/pgvector:pg16` (tag à vérifier ; la base du compose est sur un réseau interne sans port publié) ; `$env:TEST_POSTGRES_URL="postgresql+psycopg://postgres:test@127.0.0.1:5433/cadrage_test"` ; `cd backend` ; `.venv\Scripts\alembic upgrade head` ; `.venv\Scripts\pytest -q -m postgres` ; rôle `bi_reader` : `db/dw/roles.sql` (changer `CHANGER_MOI`) |
| **T2** | Licences, Ollama, première éval B | vérifier `08` §8 ; `ollama pull <modèle>` (génération et embeddings) ; renseigner `.env` (`LLM_PROVIDER=ollama`, `OLLAMA_*`) ; test de fumée `OllamaProvider` ; remplir `*_REMPLIR_T2` dans `backend/eval/configs/B.yaml` ; `cd backend` ; `.venv\Scripts\python -m eval.harness.run --config eval/configs/B.yaml` |
| **T3** | Parcours navigateur (Playwright) | `cd frontend` ; `npm install` ; `npm run build` ; `npx playwright install chromium` ; parcours : import → constats → ToR → approbation → export (à écrire avec toi) |
| **T4** | Corpus public et jeu d'entraînement | télécharger les documents, noter chaque licence dans `data/LICENCES.md` ; `cd backend` ; `.venv\Scripts\python -m training.dataset.build` (options : voir `training/README.md`) |
| **T5** | Entraînement LoRA réel, éval C vs B | `pip install -r training/requirements-train.txt` ; essai 1 % puis `python -m training.train_lora --budget-hours <h>` (profil `colab` ou `pc-nuit`, voir `training/README.md`) ; export GGUF ; `python -m eval.harness.run --config eval/configs/C.yaml` ; règle de décision de `08` §6 |
| **T6** | LibreOffice, Power BI, images Docker | `.venv\Scripts\pytest -q -m soffice` (LibreOffice installé) ; `docker compose build` ; `docker compose up -d` ; `python -m app.dw.demo --seed 42` puis `python -m app.dw.export_csv --out bi/export/` ; suivre `bi/README.md` (5 pages) ; `deploy/offline/build_bundle.ps1` |

Avant T1, vérifier chaque commande dans le README du lot concerné : plusieurs options (`--out`, graines, profils) n'ont pas été exécutées sur la machine cible.
