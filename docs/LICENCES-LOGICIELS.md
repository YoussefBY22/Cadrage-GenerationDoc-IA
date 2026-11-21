# Licences des logiciels utilisés

Règle : seulement des licences autorisant l'usage professionnel. **À vérifier de nouveau** avant chaque ajout (versions du `requirements.lock`).
Ce tableau est écrit de mémoire sur les licences connues de ces projets : **à confirmer** par lecture des fiches des paquets avant la livraison (J5).

| Composant | Version | Licence | Usage |
|---|---|---|---|
| Python | 3.12 | PSF | langage |
| FastAPI | 0.165.0 | MIT | API |
| Starlette | 1.10.0 | BSD-3-Clause | socle de FastAPI |
| Pydantic / pydantic-settings | 2.14.4 / 2.16.3 | MIT | validation, configuration |
| Uvicorn | 0.54.0 | BSD-3-Clause | serveur |
| httpx | 0.28.1 | BSD-3-Clause | client HTTP vers le modèle **local** |
| psycopg | 3.3.9 | LGPL-3.0 | accès PostgreSQL (utilisé comme bibliothèque, non modifié) |
| pytest, ruff | — | MIT | tests et lint (développement) |
| PostgreSQL | 16 | licence PostgreSQL | base |
| pgvector | image `pgvector/pgvector:pg16` | licence PostgreSQL | recherche vectorielle |

Note : `opentelemetry-api` est tiré par FastAPI/Starlette (simple API, **sans exportateur** : n'envoie rien). Le test statique interdit l'import de télémétrie dans notre code.

Modèles de langage : aucun intégré à ce stade (le choix et la licence de chaque modèle seront notés ici avant usage).
