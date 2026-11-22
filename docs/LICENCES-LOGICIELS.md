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

## Modèles et serveur de modèles (lot T2, vérifiés le 22/11/2026 par `ollama show`)

| Composant | Version / empreinte | Taille sur disque | Licence (fiche Ollama) | Usage |
|---|---|---|---|---|
| Ollama | 0.40.16 (Windows) | ~1,9 Go (installeur) | MIT | serveur local de modèles, `localhost:11434` |
| qwen3:4b | `359d7dd4bcda`, 4,0 Md de paramètres, quantification Q4_K_M, contexte natif 262 144 | 2,5 Go | Apache 2.0 | génération (sections, constats, feuille de route) |
| bge-m3 | `790764642607`, 566,7 M de paramètres, F16, 1024 dimensions, contexte 8 192 | 1,2 Go | MIT | embeddings (recherche vectorielle) |

Les deux licences autorisent l'usage commercial et professionnel. Aucune donnée n'est envoyée à l'extérieur : les modèles sont téléchargés une fois, puis exécutés localement (le garde-fou d'hôte de `OllamaProvider` n'accepte que les hôtes locaux).
