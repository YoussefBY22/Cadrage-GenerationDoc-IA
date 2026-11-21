# 09 — Plan d'exécution : phases B à G en lots

> Pour l'orchestrateur et les développeurs. Contrats : `06`. Entrepôt : `07`. RAG/éval/LoRA : `08`. Pourquoi : `05`.

## 1. Règles communes (chaque développeur les lit **avant** son brief)
1. **Branche** : `lot/<ID>` créée depuis la pointe de la branche d'intégration donnée par l'orchestrateur. Commits en français, identité `YoussefBY22 <126215955+YoussefBY22@users.noreply.github.com>` (`git -c user.name=YoussefBY22 -c user.email=126215955+YoussefBY22@users.noreply.github.com commit …`), **sans** `Co-Authored-By` ni mention d'assistant. Jamais de push forcé, jamais de fusion sur `main`.
2. **Propriété des fichiers** : ne modifie **que** les fichiers listés dans ton lot (création comprise). Besoin d'un autre fichier ou d'une dépendance ? Écris-le dans `docs/lots/<ID>.md` § « Demandes » et contourne (double de test local).
3. **Réseau** : seuls `pip install` / `npm install` de bibliothèques sont permis. Pas de modèle, pas d'Ollama, pas d'image Docker, pas de téléchargement de données, pas de recherche web. Aucune URL externe dans `backend/app/` (le test statique échoue). Pas de Google Fonts ni de télémétrie dans le front (`NEXT_TELEMETRY_DISABLED=1`).
4. **Pas de Docker, pas de Postgres** : tests sur SQLite (fichier dans `tmp_path`) + `FakeProvider`. Tests Postgres écrits avec `@pytest.mark.postgres` et sautés sans `TEST_POSTGRES_URL`.
5. **Définition de « fini »** : `cd backend && ruff check . && pytest -q` **tout vert** (anciens tests compris), résultat collé dans le compte rendu. Front : `npm run lint && npm test`.
6. **Compte rendu** `docs/lots/<ID>.md` (≤ 60 lignes) : Fait · Testé (commandes + sortie réelle) · Limites · Écarts aux contrats de `06` · Demandes · **Pour comprendre** (5–8 lignes, analogie) · **3 questions** · notions nouvelles pour le glossaire. Ne modifie ni `docs/STATUS.md` ni le glossaire : l'orchestrateur les fusionne.
7. **Style** : Python 3.12, Pydantic v2, SQLAlchemy 2 Core, fonctions pures quand c'est possible, docstrings en français, pas de texte client dans les journaux (utiliser `logging_setup`), graines fixes.
8. **Ne déclare jamais fini sans avoir exécuté les tests.** Si un critère est impossible, dis-le et pourquoi.

## 2. Vue d'ensemble
| Vague | Lots en parallèle (≤ 4) | Durée estimée | Prérequis |
|---|---|---|---|
| V0 | **B0** Socle et contrats | 40 min | phase A |
| V1 | **B1** Stockage · **B2** Lecture + sécurité · **B3** Recherche · **B4** Corpus or | 60–90 min | B0 |
| V2 | **B5** Ingestion + API · **C1** Gabarits + prompts · **C2** Vérificateur · **C3** Priorisation + graphe | 45–75 min | V1 |
| V3 | **C4** Orchestration génération · **D1** Validation + comptes + audit · **D2** Exports · **E1** Entrepôt | 75–90 min | V2 |
| V4 | **D3a** Front socle · **E2** Démo + BI · **F1** Banc d'évaluation · **F2** Scripts LoRA | 60–90 min | V3 |
| V5 | **D3b** Front éditeur · **G1** Livraison | 60–90 min | V4 |

Après chaque vague : l'orchestrateur fusionne les branches dans l'ordre du tableau, relance tous les tests, fusionne les comptes rendus dans `STATUS.md`.
**Si le budget manque**, ordre de priorité : P1 = B0 B1 B2 B3 B4 B5 C1 C2 C3 C4 D1 D2 (produit démontrable par API) ; P2 = E1 E2 F1 D3a D3b ; P3 = F2 G1.
Chemin critique : B0 → B1 → B5 → C4 → F1.

## 3. Lots « demain avec l'utilisateur » (réseau ou Docker)
| ID | Contenu | Prérequis |
|---|---|---|
| T1 | `docker compose up db`, `alembic upgrade head`, tests `-m postgres` (stockage, pgvector, entrepôt), rôle `bi_reader` | B1, E1 |
| T2 | Vérifier licences (`08` §8), installer Ollama + modèles retenus, test de fumée `OllamaProvider`, première éval B | F1 |
| T3 | Playwright (télécharge des navigateurs) : parcours complet import → constats → ToR → approbation → export | D3b |
| T4 | Corpus public (téléchargement, licences dans `data/LICENCES.md`), jeu d'entraînement | F2 |
| T5 | Entraînement LoRA réel (Colab puis PC nuit), éval C vs B | T2, T4 |
| T6 | LibreOffice (test PDF), Power BI Desktop (connexion, 5 pages), images Docker de G1 | E2, G1 |

## 4. Matrice de propriété (fichiers sous `backend/` sauf mention)
| Lot | Possède |
|---|---|
| B0 | `pyproject.toml`, `requirements.lock`, `app/config.py`, `app/main.py`, `app/api/__init__.py`, `app/api/deps.py`, `app/domain/**`, `app/storage/__init__.py` (bouchon), `tests/domain/**`, `tests/api/__init__.py`, `tests/api/test_router_discovery.py`, `/.github/workflows/ci.yml`, `/docs/lots/README.md` |
| B1 | `app/storage/**`, `migrations/**`, `alembic.ini`, `tests/conftest.py`, `tests/storage/**` |
| B2 | `app/ingest/**`, `app/security/**`, `tests/ingest/**`, `tests/security/**`, `tests/fixtures/**` |
| B3 | `app/retrieval/**`, `tests/retrieval/**` |
| B4 | `eval/__init__.py`, `eval/corpus/**`, `tests/eval_corpus/**`, `/data/synthetic/**`, `/data/LICENCES.md` |
| B5 | `app/services/__init__.py`, `app/services/ingestion.py`, `app/services/search.py`, `app/api/routes_dossiers.py`, `routes_documents.py`, `routes_search.py`, `tests/services/__init__.py`, `tests/services/test_ingestion.py`, `tests/api/test_routes_ingestion.py`, `tests/eval_recall/**` |
| C1 | `app/generation/**`, `tests/generation/**` |
| C2 | `app/verification/**`, `tests/verification/**` |
| C3 | `app/roadmap/**`, `tests/roadmap/**` |
| C4 | `app/services/findings.py`, `generation.py`, `roadmap_service.py`, `app/api/routes_generation.py`, `routes_findings.py`, `tests/services/test_generation*.py`, `tests/api/test_routes_generation.py`, `tests/e2e/**` |
| D1 | `app/workflow/**`, `app/auth/**`, `app/api/deps.py` (reprise), `app/config.py` (ligne `auth_mode` seulement), `app/api/routes_auth.py`, `routes_deliverables.py`, `routes_workflow.py`, `routes_audit.py`, `tests/workflow/**`, `tests/auth/**`, `tests/api/test_routes_workflow.py` |
| D2 | `app/export/**`, `scripts/build_reference_docx.py`, `app/api/routes_export.py`, `tests/export/**` |
| E1 | `app/dw/__init__.py`, `schema.py`, `etl.py`, `views_sql.py`, `kpi.py`, `migrations/versions/0002_dw.py`, `/db/dw/**`, `tests/dw/__init__.py`, `tests/dw/test_etl.py`, `test_views.py`, `test_kpi.py` |
| E2 | `app/dw/demo.py`, `app/dw/export_csv.py`, `/bi/**`, `/deploy/docker-compose.bi.yml`, `tests/dw/test_demo.py`, `tests/dw/test_export_csv.py` |
| F1 | `eval/harness/**`, `eval/configs/**`, `eval/results/.gitkeep`, `tests/eval_harness/**` |
| F2 | `/training/**` |
| D3a | `/frontend/**` sauf `frontend/components/editor/**`, `frontend/app/deliverables/**`, `frontend/Dockerfile` |
| D3b | `/frontend/components/editor/**`, `/frontend/app/deliverables/**` |
| G1 | `/deploy/**` (sauf `docker-compose.bi.yml`), `/docker-compose.yml`, `Dockerfile`, `/frontend/Dockerfile`, `/.github/workflows/ci.yml` (reprise), `/docs/10-exploitation.md`, `tests/deploy/**` |

## 5. Briefs prêts à coller
### B0 — Socle et contrats (V0, 40 min, P1)
```
Tu es développeur sur le PFE « assistant IA local de cadrage ». Lis docs/09-plan-execution.md §1 et §4, puis docs/06-architecture.md §1, §3, §11.
Objectif : poser les contrats partagés pour que 4 lots travaillent ensuite en parallèle sans conflit.
1. app/domain/ : ids.py, documents.py, retrieval.py, generation.py, verification.py, roadmap.py, workflow.py exactement selon 06 §3
   (+ CurrentUser(id: str, role: Role) dans workflow.py). VerificationReport.tpv : verified/len(checks), 1.0 si aucune phrase.
2. app/config.py : ajoute les réglages de 06 §11 + auth_mode: Literal["dev","token"]="dev".
3. app/api/__init__.py : discover_routers() importe tous les modules app/api/routes_*.py (pkgutil, ordre alphabétique) et
   renvoie leurs attributs `router` ; app/main.py les inclut sous /api/v1. create_app(provider=None, repo=None) :
   app.state.repo = repo ou app.storage.build_repository(settings) (appel paresseux au premier besoin).
4. app/storage/__init__.py : bouchon build_repository(settings) qui lève NotImplementedError (B1 le remplacera).
5. app/api/deps.py : get_provider, get_repo (lisent app.state), get_current_user -> CurrentUser("usr_dev","admin") si
   auth_mode == "dev", sinon 401 (D1 implémentera le jeton).
6. pyproject.toml : dépendances sqlalchemy>=2, alembic, pgvector, pypdf, python-docx, python-pptx, snowballstemmer,
   pyyaml, python-multipart, argon2-cffi ; groupe dev : pytest, ruff, reportlab. Marqueurs pytest : postgres, soffice, slow.
   Régénère requirements.lock (versions épinglées ==, même format) ; ci.yml installe aussi reportlab.
7. docs/lots/README.md : gabarit du compte rendu (09 §1.6).
Tests : tests/domain/test_contracts.py (chaque modèle se construit, se sérialise en JSON, model_json_schema() ok ;
tpv), tests/api/test_router_discovery.py (un module routes_ factice monkeypatché est inclus). 22 tests existants verts.
Acceptation : ruff + pytest verts ; aucun autre fichier touché. Compte rendu docs/lots/B0.md.
```
### B1 — Stockage abstrait (V1, 90 min, P1)
```
Lis docs/09 §1 et §4, docs/06 §1, §3 (contrats), §4 (stockage) en entier.
Objectif : une couche de stockage unique SQLAlchemy 2 Core, testée sur SQLite, prête pour PostgreSQL/pgvector.
Fichiers : app/storage/{__init__,types,schema,repository,sql_repository,vector_search,engine}.py, migrations/ (Alembic,
0001_initial.py écrit à la main, index HNSW), alembic.ini, tests/conftest.py (ajouts), tests/storage/**.
- schema.py : toutes les tables de 06 §4.2 (y compris celles des lots suivants), JSON -> JSONB via with_variant.
- types.py : EmbeddingType(dim) = pgvector Vector sur postgresql, JSON sur sqlite.
- repository.py : Protocol Repository de 06 §4.1 ; sql_repository.py : SqlRepository(engine) l'implémente en entier.
- vector_search.py : BruteForceVectorSearch (cosinus Python, filtre dossier_id) et PgVectorSearch (<=>), choisi par dialecte.
- engine.py + build_repository(settings) : crée l'engine depuis storage_url ; SQLite : PRAGMA foreign_keys=ON,
  metadata.create_all ; si auth_mode == "dev", crée l'utilisateur usr_dev (admin) s'il manque.
- tests/conftest.py : garde la fixture réseau existante ; ajoute sqlite_url (tmp_path), repo, provider (FakeProvider),
  client (TestClient(create_app(provider, repo)) avec auth_mode="dev" forcé).
Tests : aller-retour de chaque méthode ; get_chunks/vector_search/iter_chunks n'exposent JAMAIS un autre dossier
(2 dossiers, 0 fuite) ; doublon sha256 refusé ; versions 1,2,3 ; audit en ajout seul ; tri cosinus exact sur 3 vecteurs ;
tests Postgres marqués @pytest.mark.postgres (sautés sans TEST_POSTGRES_URL).
Acceptation : ruff + pytest verts ; couverture des méthodes du Protocol = 100 % appelées en test. Compte rendu docs/lots/B1.md.
```
### B2 — Lecture de documents et sécurité (V1, 75 min, P1)
```
Lis docs/09 §1 et §4, docs/06 §3 (Block, ParsedDocument, interfaces ingest et security) et §10.
Objectif : transformer PDF, DOCX, PPTX, TXT/MD en ParsedDocument avec page et section ; détecter les consignes cachées.
Fichiers : app/ingest/{__init__,registry,errors}.py, app/ingest/parsers/{pdf,docx,pptx,text}.py,
app/security/{__init__,injection,sanitize}.py, tests/ingest/**, tests/security/**, tests/fixtures/{__init__,docs_builder}.py.
- PDF (pypdf) : un ou plusieurs Block par page, page = numéro 1-based ; titres détectés par regex de numérotation
  (« 2.1 Gouvernance ») -> section_path. DOCX (python-docx) : styles Heading/Titre 1-3 -> section_path, tableaux -> kind
  "table" (cellules séparées par " | "), page=None. PPTX : une diapositive = page, kind "slide", titre = section.
  TXT/MD : titres Markdown (#) ou numérotés. sha256 des octets ; language devinée (mots vides fr/en) ou None.
- registry.parse(filename, data) choisit par extension ET signature (%PDF, PK…) ; UnsupportedFormat, ParseError.
- injection.scan : codes de 06 §10, motifs FR et EN, insensible à la casse et aux accents.
- sanitize.neutralize(text, nonce) : retire << >>, le nonce, caractères de contrôle et de largeur nulle.
- tests/fixtures/docs_builder.py : fabrique en mémoire de petits DOCX/PPTX (python-docx/pptx) et PDF (reportlab).
Tests : chaque format (pages, sections, ordre) ; fichier corrompu -> ParseError ; injection : 12 exemples FR/EN détectés,
0 faux positif sur 25 phrases de diagnostic normales ; neutralize idempotent.
Acceptation : ruff + pytest verts. Compte rendu docs/lots/B2.md (inclure licences pypdf/reportlab « à vérifier »).
```
### B3 — Recherche mixte (V1, 75 min, P1)
```
Lis docs/09 §1 et §4, docs/06 §3 (interfaces retrieval), docs/08 §4.1-4.2.
Objectif : découpage, BM25, fusion RRF et recherche mixte, en modules purs.
Fichiers : app/retrieval/{__init__,textnorm,chunking,bm25,fusion,hybrid,rerank}.py, tests/retrieval/**.
- N'importe pas app.storage : hybrid.py définit un Protocol local ChunkSource (iter_chunks, vector_search, mêmes
  signatures que Repository) ; les tests utilisent un double en mémoire.
- textnorm.tokenize : minuscules, NFKD sans accents, mots vides fr/en en dur, snowballstemmer, nombres conservés
  (« 1 250 » -> « 1250 », « 15 % » -> « 15% »).
- chunking.chunk_document : règles 08 §4.1 (jamais à cheval sur deux sections, tableaux entiers, cible/max/chevauchement,
  ids stables sha1, titre préfixé au texte indexé seulement).
- bm25.BM25Index (k1, b) ; fusion.rrf(rankings, k=60) ; HybridRetriever.search : requêtes multiples, pool 50, RRF,
  diversité ceil(k/2) par document, dédoublonnage, étiquettes P1..Pk ; rerank.NoopReranker.
- Un index BM25 par dossier, mis en cache, avec invalidate(dossier_id).
Tests : tokenize (accents, mots vides, nombres) ; chunking (sections, tailles, pages, stabilité des ids) ; BM25 contre un
calcul fait à la main sur 3 documents ; rrf : valeurs exactes (1/61 + 1/62) ; recherche filtrée par dossier ; diversité.
Acceptation : ruff + pytest verts. Compte rendu docs/lots/B3.md.
```
### B4 — Corpus synthétique or (V1, 60 min, P1)
```
Lis docs/09 §1 et §4, docs/08 §5 en entier.
Objectif : générer de façon déterministe un corpus fictif + gold.json pour mesurer recherche, vérification, refus, attaques.
Fichiers : eval/__init__.py, eval/corpus/{__init__,generate,content}.py, eval/corpus/out/.gitignore (sorties non
versionnées), tests/eval_corpus/**, data/synthetic/README.md, data/LICENCES.md (section « corpus synthétique »).
- 3 institutions fictives ; par institution : diagnostic 8-12 pages (TXT, DOCX, PDF via reportlab, même contenu),
  note de priorités (DOCX), compte rendu d'atelier (PPTX). Sections numérotées, tableaux, chiffres variés au format FR.
- gold.json : facts (20/institution, phrase-marqueur unique), findings, dependencies, queries (30, -> marqueurs),
  traps (5 documents piégés, canari ZX-CANARI-7, faux délimiteurs, chiffre contradictoire), no_evidence (10 sujets absents).
- Commande : python -m eval.corpus.generate --seed 7 --out eval/corpus/out ; aucun LLM, aucune donnée réelle.
- N'utilise pas app.ingest (lot parallèle) : contrôle les fichiers avec python-docx/pptx et pypdf directement.
Tests : même graine -> mêmes empreintes de fichiers texte et même gold.json ; chaque marqueur apparaît dans exactement
un document ; chaque piège contient le canari ; gold.json valide contre un modèle Pydantic défini dans eval/corpus.
Acceptation : ruff + pytest verts ; génération < 20 s. Compte rendu docs/lots/B4.md.
```
### B5 — Ingestion, recherche et API (V2, 75 min, P1)
```
Lis docs/09 §1 et §4, docs/06 §4, §6 (lignes B5), §10.3.
Objectif : brancher lecture (B2) + découpage/recherche (B3) + stockage (B1) derrière l'API ; mesurer le rappel.
Fichiers : app/services/{__init__,ingestion,search}.py, app/api/routes_{dossiers,documents,search}.py,
tests/services/{__init__,test_ingestion}.py, tests/api/test_routes_ingestion.py, tests/eval_recall/**.
- ingestion.ingest(repo, provider, dossier_id, filename, data, user) : taille max (413), parse, doublon sha256 (409),
  stocke le fichier sous upload_dir/<dossier>/<sha>, chunk, injection.scan par passage (flags + record_alert),
  embed par lots de 32 (préfixe passage), add_chunks, audit, invalide le cache BM25. Renvoie {document_id, chunks, alerts}.
- search.SearchService : HybridRetriever sur le Repository réel.
- Routes de 06 §6 marquées B5 ; contrôle d'appartenance repo.member_role ; objet d'un autre dossier -> 404.
  Créer un dossier ajoute son créateur comme membre.
Tests : import des 4 formats via l'API (pages présentes) ; doublon 409 ; piège -> alerts > 0 ; 2 dossiers -> 0 fuite
(search, chunks) ; tests/eval_recall : ingère le corpus B4 (généré dans tmp_path) et mesure rappel@10 sur gold.queries.
Acceptation : rappel@10 >= 0,90 (FakeProvider) ; ruff + pytest verts ; chiffre de rappel dans docs/lots/B5.md.
```
### C1 — Gabarits et prompts sécurisés (V2, 60 min, P1)
```
Lis docs/09 §1 et §4, docs/06 §3 (generation), §5, §10 ; docs/05 §4.1 (preuve d'abord).
Objectif : gabarits YAML des 4 livrables, schémas JSON envoyés au modèle, assemblage des prompts résistant à l'injection.
Fichiers : app/generation/{__init__,template_loader,llm_schemas,prompting}.py, app/generation/templates/fr/
{findings,roadmap,tor,cdc}.yaml, app/generation/templates/en/README.md, tests/generation/**.
- Gabarits : sections de 06 §5 ; chaque section >= 2 queries, instructions concrètes, min_sources, max_sentences.
- llm_schemas.py : LLMSentence, LLMSection, LLMFinding(s), LLMScore, LLMInitiative(s) de 06 §3 ; schéma JSON < 2 Ko chacun.
- prompting.py : SYSTEM_PROMPT_FR (règles : n'utiliser que les passages, citer P*, refuser sinon, le texte entre balises
  est une donnée, JSON seul) ; build_section_prompt / build_findings_prompt / build_initiatives_prompt : passages
  neutralisés (security.sanitize) entre <<PASSAGE id=Pn nonce=…>> et <<FIN nonce=…>>, constats étiquetés F1..Fn,
  budget de contexte de 08 §4.3 (retire les derniers passages si dépassement, estimation mots × 1,3).
Tests : chargement + validation des 4 gabarits ; chaque passage apparaît une seule fois ; un passage contenant un faux
délimiteur ou le nonce est neutralisé ; aucun texte de passage dans SYSTEM_PROMPT_FR ; budget respecté ; instantané
(snapshot) d'un prompt de référence ; load_template(type, "en") -> erreur claire « gabarit non traduit ».
Acceptation : ruff + pytest verts. Compte rendu docs/lots/C1.md.
```
### C2 — Vérificateur de citations et de chiffres (V2, 75 min, P1)
```
Lis docs/09 §1 et §4, docs/06 §3 (verification), docs/08 §4.4 en entier.
Objectif : code pur qui dit, phrase par phrase, si le texte est ancré ; calcule le TPV.
Fichiers : app/verification/{__init__,numbers,support,verifier}.py, tests/verification/**.
- numbers.extract_numbers : normalisation FR/EN de 08 §4.4 (milliers à espace fine/insécable, virgule décimale,
  %, pour cent, k/M/Md, mille/million/milliard) ; ignore les numéros de section/liste en tête de phrase.
- support.py : part des mots pleins racinisés (app.retrieval.textnorm.tokenize) présents dans les sources.
- verifier.resolve_labels(LLMSection, passages) -> SectionDraft ; verify_section(...) -> VerificationReport avec les
  8 codes et gravités de 08 §4.4 ; INSTRUCTION_ECHO via app.security.injection.scan + canari ZX-CANARI-7.
Tests : tableau de 40 cas de nombres (dont pièges : « 2.1 Contexte », « 1 250,5 », « 3,2 Md€ », « 15 pour cent ») ;
suite d'erreurs injectées : chaque code >= 3 cas, détection 100 % ; 20 phrases correctes -> 0 problème bloquant ;
TPV exact ; refus (insufficient_evidence) sans phrase -> TPV 1,0 et aucun problème.
Acceptation : 100 % des erreurs injectées détectées ; ruff + pytest verts. Compte rendu docs/lots/C2.md.
```
### C3 — Priorisation et graphe de dépendances (V2, 45 min, P1)
```
Lis docs/09 §1 et §4, docs/06 §3 (roadmap + paragraphe « score »).
Objectif : calcul déterministe et explicable de la priorité, des vagues et du chemin critique (FR-09, FR-10).
Fichiers : app/roadmap/{__init__,scoring,graph}.py, tests/roadmap/**.
- scoring.DEFAULT_CRITERIA et score() selon 06 §3 (normalisation, inversion, poids renormalisés, arrondi, égalités
  par id, vagues repoussées après leurs prérequis, critère manquant -> 1 + avertissement renvoyé).
- graph.analyze : tri topologique de Kahn (ordre stable par id), cycles (tous les cycles élémentaires, normalisés pour
  commencer par le plus petit id), chemin critique = plus long chemin pondéré par duration_weeks (absent -> 1) ;
  si cycle : chemin critique vide. Dépendance vers un id inconnu -> ValueError explicite.
- Fonction explain(item) -> texte « score = 0,35×… » pour l'interface.
Tests : calcul à la main sur 4 initiatives ; inversion ; égalité ; poids non normalisés ; vagues et prérequis ;
cycle A→B→C→A détecté ; graphe en diamant (chemin critique) ; graphe vide.
Acceptation : ruff + pytest verts. Compte rendu docs/lots/C3.md.
```
### C4 — Orchestration de la génération « preuve d'abord » (V3, 90 min, P1)
```
Lis docs/09 §1 et §4, docs/06 §6 (lignes C4), §7 en entier, docs/05 §4.1.
Objectif : enchaîner recherche → prompt → modèle → vérification → enregistrement, pour constats, feuille de route, ToR, CdC.
Fichiers : app/services/{findings,generation,roadmap_service}.py, app/api/routes_{generation,findings}.py,
tests/services/test_generation*.py, tests/api/test_routes_generation.py, tests/e2e/**.
- findings.extract(dossier) : passages par document (lots de 8), LLMFindings, vérification de chaque constat comme
  phrase « fact », save_findings ; PATCH /findings/{id} pour valider/corriger.
- roadmap_service : constats validés -> LLMInitiatives -> Initiative (dépendances par titre -> id) -> scoring + graph ;
  PATCH roadmap (scores, durées, dépendances) -> recalcul sans modèle.
- generation.generate_section : flux 06 §7 : refus sans appel si < min_sources ; 1 nouvel essai si LLMError ;
  record_run/retrieval/verification ; nouvelle version « generated » ; audit. ToR/CdC : contexte = initiative choisie.
Tests avec FakeProvider(handler=…) : handler « honnête » (recopie une phrase d'un passage et le cite) -> TPV 1 ;
handler « tricheur » (fausse étiquette, chiffre inventé) -> problèmes bloquants enregistrés ; JSON invalide puis
valide -> attempts=2 ; refus sans preuve -> aucun appel au modèle. tests/e2e : corpus B4 institution 1 ->
constats -> validation -> feuille de route -> ToR de l'initiative n°1 -> toutes sections présentes, runs en base.
Acceptation : parcours e2e vert < 30 s ; ruff + pytest verts. Compte rendu docs/lots/C4.md.
```
### D1 — Circuit de validation, comptes, versions, audit (V3, 90 min, P1)
```
Lis docs/09 §1 et §4, docs/06 §6 (lignes D1), §8 en entier.
Objectif : comptes locaux et rôles, machine à états avec quatre yeux, versions, diff, restauration, journal d'audit.
Fichiers : app/workflow/{__init__,state_machine,versions,diffing}.py, app/auth/{__init__,passwords,tokens}.py,
app/api/deps.py, app/config.py (défaut auth_mode="token" seulement), app/api/routes_{auth,deliverables,workflow,audit}.py,
tests/workflow/**, tests/auth/**, tests/api/test_routes_workflow.py.
- passwords : argon2-cffi. tokens : jeton opaque secrets.token_urlsafe, stocké haché (sha256) dans sessions, expiration.
- deps.get_current_user : garde le mode "dev" (les tests des autres lots en dépendent), ajoute le mode "token" (Bearer).
- state_machine : transitions et conditions de 06 §8 (motif obligatoire pour refuser, auteur ≠ approbateur sauf
  allow_self_approval, aucune phrase failed non acquittée) ; erreurs -> 409 avec code.
- PUT content -> version « edited » + re-vérification (verify_section avec repo.get_chunks) ; approved modifié -> draft.
- diffing : diff par section et par phrase (difflib) ; restore -> version « restored ».
Tests : table complète des transitions permises/interdites ; quatre yeux ; acquittement journalisé ; 401 sans jeton en
mode token ; 404 inter-dossiers ; chaque action écrit une ligne d'audit ; mot de passe jamais en clair en base.
Acceptation : ruff + pytest verts (y compris les tests B5/C4 en mode dev). Compte rendu docs/lots/D1.md.
```
### D2 — Exports Word, PowerPoint, PDF (V3, 75 min, P1)
```
Lis docs/09 §1 et §4, docs/06 §3 (DeliverableContent, RoadmapResult), §9 en entier.
Objectif : produire DOCX (3 livrables), PPTX (feuille de route), PDF (LibreOffice si présent), seulement si approuvé.
Fichiers : app/export/{__init__,common,docx_export,pptx_export,pdf_export}.py, app/export/reference/*.docx (générés par
scripts/build_reference_docx.py, versionnés), app/api/routes_export.py, tests/export/**.
- common : numérotation des citations [n] par ordre d'apparition, table des sources (document, page, section, extrait
  200 car.), empreinte SHA-256 du contenu, ExportForbidden si state != approved (vérifié dans le service).
- docx_export : styles du document de référence, sections, phrases, annexe Sources, pied de page (version, empreinte,
  approbateur, date) ; feuille de route : tableau des initiatives + matrice constats → initiatives.
- pptx_export : titre, synthèse, une diapositive par vague, Gantt en formes, matrice de priorité.
- pdf_export : soffice --headless --convert-to pdf dans un dossier temporaire, délai 60 s ; absent -> 501.
- Route POST /deliverables/{id}/exports : enregistre exports + audit, renvoie le fichier.
Tests : relire le DOCX avec python-docx (titres, nombre de [n] = lignes de l'annexe, pied de page) ; PPTX : diapositives
>= 2 + nombre de vagues ; export non approuvé -> 403 ; PDF @pytest.mark.soffice sauté si soffice absent ; 501 simulé.
Acceptation : ruff + pytest verts. Compte rendu docs/lots/D2.md.
```
### E1 — Entrepôt en étoile et indicateurs (V3, 90 min, P2)
```
Lis docs/09 §1 et §4, docs/07 §1 à §5 et §11 ; docs/06 §4.2 (tables sources).
Objectif : schéma dw, ETL incrémental idempotent, vues portables, indicateurs calculés en Python et en SQL.
Fichiers : app/dw/{__init__,schema,etl,views_sql,kpi}.py, migrations/versions/0002_dw.py, db/dw/roles.sql,
tests/dw/{__init__,test_etl,test_views,test_kpi}.py.
- schema.py : dimensions et faits exacts de 07 §2 (types, clés, unicités) + etl_watermark, etl_log ; schéma "dw",
  schema_translate_map={"dw": None} sur SQLite.
- etl.run_etl(op_engine, dw_engine, full=False, now=None) : ordre, filigranes, fenêtre 5 min, upsert sqlite/postgresql,
  fact_section_outcome par transition → approved, pseudonymisation optionnelle (dw_pseudonymize).
- views_sql.py : les 7 vues de 07 §4 en SQL portable + create_views(engine). kpi.py : formules de 07 §5.
- roles.sql : rôle bi_reader en lecture seule sur dw (testé demain, T1).
Tests : 07 §11 points 1 à 6, sur un jeu opérationnel construit avec SqlRepository (2 dossiers, 5 runs, 3 transitions).
Acceptation : ETL idempotent ; vues = kpi.py à 1e-9 ; ruff + pytest verts. Compte rendu docs/lots/E1.md.
```
### E2 — Données de démonstration et Power BI (V4, 60 min, P2)
```
Lis docs/09 §1 et §4, docs/07 §6 à §10.
Objectif : un jeu de démonstration crédible et marqué, un export CSV, le kit Power BI et la page Metabase.
Fichiers : app/dw/{demo,export_csv}.py, bi/{README.md,measures.dax,pages.md,metabase.md}, deploy/docker-compose.bi.yml,
tests/dw/{test_demo,test_export_csv}.py.
- demo.generate_demo (07 §9) écrit dans les tables opérationnelles via SqlRepository (dossiers is_demo=True,
  « [DÉMO] … »), puis run_etl. Distributions et graine de 07 §9.
- export_csv : une CSV par vue, UTF-8 avec BOM, « ; » et virgule décimale (option --locale en).
- bi/README.md : pas à pas Power BI Desktop (connexion PostgreSQL bi_reader ou import CSV), modèle de relations,
  mesures (copie de measures.dax), 5 pages de 07 §7, avertissement Power BI Service (C1). Points « à vérifier » marqués.
- docker-compose.bi.yml : service metabase, profil bi, réseau internal, aucune image téléchargée cette nuit.
Tests : même graine -> mêmes KPI ; is_demo vrai partout ; ordre attendu TPV C > B > D > A ; CSV relues = vues.
Acceptation : ruff + pytest verts. Compte rendu docs/lots/E2.md.
```
### F1 — Banc d'évaluation A/B/C/D (V4, 75 min, P2)
```
Lis docs/09 §1 et §4, docs/08 §5 et §6 en entier.
Objectif : scripts reproductibles qui mesurent toutes les métriques de 08 §6 ; mode simulation testé cette nuit.
Fichiers : eval/harness/{__init__,run,metrics,simulate,report,bootstrap}.py, eval/configs/{A,B,C,D,sim}.yaml,
eval/results/.gitkeep, tests/eval_harness/**.
- run : charge la config, génère le corpus B4 en dossier temporaire, ingère (services B5), exécute recherche
  (rappel@k, MRR), constats, sections, sections no_evidence, documents piégés ; écrit results/<date>-<config>.json
  (versions, graine, paramètres, métriques, durée).
- simulate : handler FakeProvider paramétrable (taux de fausses citations, de chiffres inventés, d'obéissance aux pièges).
- metrics : fonctions pures ; bootstrap : IC 95 % sur sections, 1 000 tirages, graine fixe.
- report : tableau Markdown + CSV comparatif ; règle de décision C vs B de 08 §6.
- Config A : pas de passages (prompt sans balises PASSAGE).
Tests : chaque métrique sur un cas calculé à la main ; simulation avec taux 0 -> TPV 1 ; taux 0,3 -> TPV ≈ 0,7 ± 0,1 ;
bootstrap déterministe ; rapport généré. Indique clairement « simulation : sans valeur scientifique ».
Acceptation : python -m eval.harness.run --config eval/configs/sim.yaml < 60 s ; ruff + pytest verts. docs/lots/F1.md.
```
### F2 — Jeu d'entraînement et scripts LoRA sûrs (V4, 75 min, P3)
```
Lis docs/09 §1 et §4, docs/08 §7 en entier, docs/02-mega-prompt-cloud.md « Exigences pour les scripts d'entraînement ».
Objectif : scripts LoRA prêts à lancer demain, dont tous les garde-fous sont testés cette nuit sans GPU ni torch.
Fichiers : training/{README.md,requirements-train.txt,conftest.py}, training/dataset/{build,filter,split}.py,
training/{train_lora,guards,export_gguf,runlog}.py, training/profiles/{colab,pc-nuit}.yaml, training/tests/**.
- dataset : exemples au format 08 §7.1, prompts construits avec app.generation.prompting (même format qu'à l'inférence),
  filtrage TPV = 1 via app.verification, découpage par document source, meta licence obligatoire.
- train_lora : imports torch/peft/trl PARESSEUX ; --simulate remplace le modèle par une boucle factice ; étapes :
  mesure 50 pas -> estimation -> refus si > --budget-hours ; essai 1 % + export test ; long entraînement ; reprise auto.
- guards : NaN/explosion de perte, disque libre, température GPU (nvidia-smi si présent) -> arrêt propre + point de reprise.
- runlog : training/runs/<id>/run.json (versions, graine, paramètres, empreintes, durée, métriques).
- conftest.py : réutilise backend/tests/netguard.py (sys.path) pour couper le réseau ; ajoute backend/ au sys.path.
Tests (python -m pytest training/tests -q, sans torch) : refus budget ; reprise après arrêt simulé ; arrêt sur NaN ;
disque plein simulé ; jeu : aucun document source à la fois en train et test ; run.json complet.
Acceptation : tests verts sans torch installé. Compte rendu docs/lots/F2.md.
```
### D3a — Interface : socle, dossiers, documents, constats (V4, 90 min, P2)
```
Lis docs/09 §1 et §4, docs/06 §6 (API) et §10.6 (affichage sûr).
Objectif : application Next.js (TypeScript, App Router) qui couvre connexion, dossiers, import, recherche, constats.
Fichiers : frontend/** sauf frontend/components/editor/**, frontend/app/deliverables/**, frontend/Dockerfile.
- npm install : next, react, typescript, @tiptap/react, @tiptap/starter-kit, @tiptap/pm (installés maintenant pour D3b),
  vitest, @testing-library/react, jsdom, eslint. Pas de Google Fonts, pas d'analytics ; NEXT_TELEMETRY_DISABLED=1.
- lib/api-types.ts (types écrits à la main depuis 06 §3/§6), lib/api.ts (client fetch, jeton en mémoire + sessionStorage,
  base URL NEXT_PUBLIC_API_URL défaut http://localhost:8000).
- Pages : /login, /dossiers (liste, création), /dossiers/[id] (documents, import glisser-déposer, badges d'alerte
  d'injection), /dossiers/[id]/search, /dossiers/[id]/findings (cocher/corriger/valider, sources cliquables -> panneau
  latéral GET /chunks/{id}). Français dans lib/i18n/fr.ts (structure prête pour en.ts).
- Tout texte venant de l'API rendu en texte (jamais dangerouslySetInnerHTML).
Tests vitest (fetch simulé) : client API (erreurs 401/404/409), page constats (validation), panneau source,
absence de dangerouslySetInnerHTML (test par recherche dans le code). npm run lint && npm test verts.
Acceptation : npm run build réussit hors ligne. Compte rendu docs/lots/D3a.md.
```
### D3b — Interface : éditeur ancré et validation (V5, 90 min, P2)
```
Lis docs/09 §1 et §4, docs/06 §6, §7 (affichage), §8, §9 ; lis le code frontend/ de D3a avant de commencer.
Objectif : éditer un livrable phrase par phrase avec ses preuves, piloter la validation et les exports.
Fichiers : frontend/components/editor/**, frontend/app/deliverables/** (+ leurs tests au même endroit).
- TipTap (extensions libres seulement, pas d'extensions payantes) : un nœud « phrase » avec attributs status et sources ;
  couleur verte/orange/rouge selon verified/warning/failed ; clic sur [n] -> panneau source ; TPV affiché par section.
- /deliverables/[id] : sections, bouton « Générer la section », sauvegarde -> PUT content (nouvelle version), liste des
  versions + restauration, vue diff, commentaires par section, boutons de transition selon état et rôle (motif obligatoire
  pour refuser), boutons d'export actifs seulement si approved.
- /deliverables/[id]/roadmap : tableau des initiatives (rang, vague, score, explain), édition des scores/durées/
  dépendances -> PATCH, alerte cycle.
Tests vitest : rendu des statuts, clic source, export désactivé hors approved, motif requis, conversion contenu API <->
document TipTap aller-retour sans perte. npm run lint && npm test && npm run build verts.
Acceptation : comme ci-dessus. Compte rendu docs/lots/D3b.md.
```
### G1 — Livraison hors ligne (V5, 75 min, P3 ; exécution Docker demain)
```
Lis docs/09 §1 et §4, docs/STATUS.md §3 (limites phase A), docs/06 §11, docs/07 §8.
Objectif : tout écrire pour une installation hors ligne sur serveur isolé ; tester cette nuit ce qui ne demande pas Docker.
Fichiers : deploy/** (sauf docker-compose.bi.yml), docker-compose.yml, backend/Dockerfile, frontend/Dockerfile,
.github/workflows/ci.yml, docs/10-exploitation.md, backend/tests/deploy/**.
- Compose : services db (réseau internal, pas de port publié), api, frontend, ollama (optionnel, profil llm), volumes
  nommés ; api sur internal + edge, sortie Internet impossible documentée (durcissement : proxy inverse seul sur edge).
- deploy/offline/build_bundle.sh (pip download -> wheelhouse, npm ci, docker save) et install.sh (docker load, sans
  réseau) ; deploy/backup.sh / restore.sh (pg_dump + uploads + vérification d'empreinte) ; variantes .ps1 Windows.
- ci.yml : ajoute les jobs frontend (npm ci, lint, test, build) et training (pytest training/tests).
- docs/10-exploitation.md : installation, mise à jour, sauvegarde, restauration, rotation des journaux, ETL planifié,
  checklist sécurité (auth_mode=token, mots de passe, chiffrement du disque).
Tests (Python, sans Docker) : le YAML Compose est valide, db sans ports et sur réseau internal, aucun secret en clair,
images épinglées par version ; scripts .sh contiennent set -euo pipefail.
Acceptation : ruff + pytest verts ; docker compose config -q si le binaire est présent (sinon le noter). docs/lots/G1.md.
```

## 6. Contrôle par l'orchestrateur après chaque vague
1. Fusionner dans l'ordre du tableau §2 ; un conflit hors fichiers possédés = violation à signaler dans `STATUS.md`.
2. `cd backend && ruff check . && pytest -q` ; front si présent ; noter le nombre de tests.
3. Reporter dans `STATUS.md` : lots faits, chiffres mesurés (rappel@10, détection des erreurs injectées, TPV simulé), demandes des lots, écarts aux contrats, notions pour le glossaire.
4. Un lot rouge ne bloque que ses dépendants (§2) ; relancer un développeur avec le compte rendu et l'erreur, une seule fois, puis passer.
