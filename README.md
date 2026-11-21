# PFE — Assistant IA local de cadrage

**Sujet** : *Stages & PFE Book 2026-2027*, p. 92, **Réf. #TST 11** — conception d'un outil IA de génération de feuilles de route, de termes de référence et de cahiers des charges.

## En quelques lignes

Les consultants rédigent souvent les mêmes documents à partir de diagnostics : **feuilles de route**, **termes de référence**, **cahiers des charges**. On construit un assistant qui prépare un **premier jet** à partir des documents du client, **cite chaque source**, **vérifie lui-même** que les sources et les chiffres existent, puis laisse le consultant **relire, corriger et valider** dans un éditeur avant d'exporter en Word, PowerPoint ou PDF.

Comme les documents sont confidentiels, **tout tourne sur le serveur du client**, avec un modèle de langage **ouvert**, sans API ni cloud. Le modèle apprend **comment rédiger** (fine-tuning léger sur des documents **publics**) et trouve **les faits** dans les documents du client au moment de répondre (**RAG**). Un **entrepôt de données** et un **tableau de bord** (Power BI) mesurent l'usage et la qualité.

## Ce qu'on fait, concrètement

1. **Cloud (le développement)** : une session Claude Code cloud écrit **tout le code**, sans GPU, avec un **faux modèle** qui permet de tout tester. Elle suit `docs/02-mega-prompt-cloud.md`.
2. **Chez toi (plus tard)** : tu installes un vrai modèle local, on le branche, puis on mesure.
3. **Entraînement** : sur un GPU gratuit (données publiques seulement) ou la nuit sur ton PC. Les scripts mesurent la durée **avant** de démarrer et reprennent après une panne.
4. **Chez l'entreprise (au PFE)** : même produit, modèle plus grand, entraînement réel sur leur serveur.

## Ce que tu envoies au cloud

Rien d'autre que ce dépôt privé `PRV-PR8-PFE-IA-Cadrage` : le cahier des charges, le méga prompt et ce guide. Aucun document personnel ou client. Tu ouvres la session sur ce dépôt et tu colles le méga prompt.

## Ce que tu télécharges (sans urgence, ton PC peut se reposer)

À faire quand le code sera prêt ; je te redonnerai les commandes exactes.

| Élément | Rôle | Ordre de grandeur |
|---|---|---|
| **Ollama** | Fait tourner un modèle en local | quelques centaines de Mo |
| **Un petit modèle** (par exemple Qwen3 ≈ 1,7 B ou Ministral 3 ≈ 3 B) | Rédiger | 1 à 3 Go |
| **Un modèle d'embeddings multilingue** | Chercher par le sens | ≈ 1 à 2 Go |
| **LibreOffice** | Convertir en PDF | ≈ 0,5 Go |
| **Docker Desktop** | Déjà installé chez toi | — |
| **Power BI Desktop** | Tableau de bord | déjà installé chez toi |

Tu as environ 35 Go libres sur ton disque : garde de la marge.

## Démarrage rapide (Windows, PowerShell)

Prérequis : Python 3.12, Node 22. Aucun modèle ni Docker nécessaire : le faux modèle suffit pour tout tester.

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e . pytest ruff reportlab
.venv\Scriptsuff check .
.venv\Scripts\pytest -q
```
Résultat attendu : `All checks passed!` puis 388 passed, 2 skipped (PostgreSQL et LibreOffice absents). Tests d'entraînement : `.venv\Scripts\python -m pytest ..	raining	ests -q`.

Lancer l'API (SQLite local, faux modèle, mode `dev` sans connexion) :
```powershell
cd backend
$env:AUTH_MODE="dev"
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```
Santé : http://localhost:8000/health. Les routes sont sous `/api/v1`.

Lancer l'interface (autre terminal) :
```powershell
cd frontend
npm install
$env:NEXT_TELEMETRY_DISABLED="1"
npm run dev
```
Ouvrir http://localhost:3000 (`NEXT_PUBLIC_API_URL` vaut `http://localhost:8000` par défaut). Tests du front : `npm run lint ; npm test ; npm run build`.

Corpus synthétique, banc d'évaluation simulé et données de démonstration :
```powershell
cd backend
.venv\Scripts\python -m eval.corpus.generate --seed 7 --out eval/corpus/out
.venv\Scripts\python -m eval.harness.run --config eval/configs/sim.yaml
.venv\Scripts\python -m app.dw.demo --seed 42
```

## Arborescence

```
backend/app/        api, domain (contrats), storage, ingest, security, retrieval, generation,
                    verification, roadmap, workflow, auth, export, dw (entrepôt), services, llm
backend/eval/       corpus/ (corpus or), harness/ (banc A/B/C/D), configs/
backend/tests/      un dossier par module ; migrations/ (Alembic)
frontend/           Next.js 15 (dossiers, éditeur ancré, feuille de route)
training/           jeu d'entraînement et scripts LoRA (simulation sans GPU)
bi/                 Power BI / Metabase : mesures DAX, pages, pas à pas
deploy/             nginx, sauvegarde/restauration, paquet hors ligne, compose BI
db/                 init PostgreSQL, rôle bi_reader (dw/)
data/               corpus synthétique et LICENCES.md
docs/               documents 01 à 10, STATUS.md, lots/ (comptes rendus)
```

## Documents

| Doc | Contenu |
|---|---|
| `docs/01-cahier-des-charges.md` | besoin, exigences |
| `docs/02-mega-prompt-cloud.md` | consignes du développement cloud |
| `docs/03-apprentissage-et-glossaire.md` | glossaire et plan d'apprentissage |
| `docs/04-phase-A-comprendre.md` | comprendre la phase A (squelette) |
| `docs/05-revue-perimetre.md` | revue du périmètre |
| `docs/06-architecture.md` | architecture, contrats, API |
| `docs/07-entrepot-bi.md` | entrepôt en étoile, indicateurs, Power BI |
| `docs/08-modele-rag-evaluation.md` | modèles, RAG, vérification, évaluation, entraînement |
| `docs/09-plan-execution.md` | lots, propriété des fichiers, briefs |
| `docs/10-exploitation.md` | installation hors ligne, sauvegarde, sécurité |
| `docs/STATUS.md` | état d'avancement, chiffres, prochaines étapes |
| `docs/lots/` | comptes rendus de chaque lot et index « Pour comprendre » |

## Comment on travaille ensemble

- **Session cloud** : construit, teste, écrit `docs/STATUS.md`.
- **Toi** : tu lis `STATUS.md` et les « Pour comprendre », tu tranches les décisions, tu lances les essais sur ton PC.
- **Cette conversation GitHub** : on la garde pour la gestion des dépôts et du profil. Pour le PFE, on ouvre **une nouvelle conversation**, avec ce dépôt comme point de départ.

## Ce que tu dois comprendre

Lis `docs/03-apprentissage-et-glossaire.md` : glossaire en français simple (jeton, température, RAG, fine-tuning…), plan sur 8 semaines synchronisé avec le projet, et les compétences par ordre d'urgence.

## Ordre de lecture

1. Ce fichier
2. `docs/03-apprentissage-et-glossaire.md` (le glossaire d'abord)
3. `docs/01-cahier-des-charges.md`
4. `docs/02-mega-prompt-cloud.md` (c'est ce qu'on envoie)
5. `docs/STATUS.md` (où en est le projet), puis `docs/04` à `docs/10` selon les besoins
