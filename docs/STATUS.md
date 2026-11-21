# STATUS — Phase A « Squelette » (21/11/2026)

Branche : `claude/exciting-volta-qipfkc` (imposée par l'environnement ; une branche par phase sera créée à partir de la phase B si tu le préfères).

## 1. Fait
- Dépôt structuré : `backend/` (FastAPI, Python 3.12), `db/init/`, `docker-compose.yml`, `.env.example`, CI GitHub Actions sans GPU.
- Interface `LLMProvider` (texte, JSON contraint, embeddings) + `FakeProvider` déterministe (scriptable pour simuler un modèle qui triche) + `OllamaProvider` (réel, garde-fou : hôte local uniquement).
- API : `/health`, `/ready` (vérifie la base **et** l'extension pgvector ; ne divulgue jamais l'URL/mot de passe).
- Journalisation JSON qui remplace tout contenu sensible (`prompt`, `text`, `passage`…) par une empreinte.
- Test « aucune connexion sortante » : garde dynamique (toute connexion/DNS non local fait échouer **chaque** test) + scan statique (imports cloud/télémétrie, URL externes) + test du scanner lui-même.
- Docker Compose : base sur un réseau `internal` (aucune route vers Internet).
- Glossaire complété ; `docs/LICENCES-LOGICIELS.md`, `data/LICENCES.md`.

## 2. Testé (résultats réels)
```
cd backend && .venv/bin/ruff check .   -> All checks passed!
cd backend && .venv/bin/pytest -q      -> 22 passed
```
Docker (démon lancé dans le conteneur) : `docker compose up --build -d` -> `api` et `db` **healthy** ;
`curl localhost:8000/ready` -> `{"status":"ok","database":"ok","llm_provider":"fake-v1"}` (pgvector bien présent) ;
depuis le conteneur `db` : connexion vers 1.1.1.1:443 -> « Network is unreachable ».
`docker compose config -q` valide.

## 3. Pas encore fait / limites
- `OllamaProvider` jamais lancé avec un vrai Ollama (contrat seulement, serveur simulé). Les noms de modèles sont à fournir dans `.env`.
- Dans ce bac à sable, `docker compose up --build` du dépôt **échoue au `pip install`** (le proxy du cloud ré-signe le TLS). J'ai validé avec un Dockerfile temporaire identique + certificat du proxy, hors dépôt. Sur ton PC / la CI, le Dockerfile normal doit passer, mais **je ne l'ai pas vu passer tel quel**.
- La CI GitHub Actions n'a pas encore tourné (elle ne se déclenche qu'après le push).
- Les licences du tableau sont écrites de mémoire : à confirmer.
- Le garde-fou réseau protège les tests, pas le conteneur en production : en production, c'est le réseau `internal` + l'absence de bibliothèque cloud qui protègent. L'API est sur le réseau `edge` pour publier son port (et peut techniquement sortir) ; durcissement possible en phase G.
- Migrations SQL versionnées : phase B (pour l'instant seulement `CREATE EXTENSION vector`).

## 4. Décisions à prendre par moi
1. **Branches** : l'environnement impose `claude/exciting-volta-qipfkc`. Veux-tu des branches `phase-b-…`, etc. (je ne peux pousser que sur la branche autorisée sans ton accord) ?
2. **Langue des documents** : français seul au départ (hypothèse) ou français + anglais dès la phase B ?
3. **Corpus public de la phase B** : OK pour que je prenne quelques documents de bailleurs sous licence ouverte (si l'accès réseau le permet), sinon corpus 100 % synthétique ?

## 5. Prochaine étape
Phase B : migrations SQL, import PDF/DOCX/PPTX/TXT avec page et section, découpage, index BM25 + vecteurs, fusion, tests de rappel.
