# API « Modèles » (administrateur)

Préfixe `/api/v1`. Tous les points sont réservés au rôle `admin` (403 `FORBIDDEN_ROLE` sinon). Le moteur n'est lu qu'en lecture (`/api/tags`, `/api/show`, `/api/ps`) ; rien n'est téléchargé. L'adresse du moteur vient de `OLLAMA_BASE_URL` (liste d'hôtes locaux `LLM_ALLOWED_HOSTS`).

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/admin/models` | `ModelsOverview` : modèles installés, actif, précédent, historique, limites, budget de contexte |
| GET | `/admin/models/context?candidate_tokens=N` | `ContextBudget` pour une section dont les passages retrouvés pèsent N jetons |
| POST | `/admin/models/test` `{model}` | `TestReport` (conservé dans le registre) |
| POST | `/admin/models/activate` `{model, role?}` | exige un test réussi **et à jour** ; journalisé (`model.activate`) |
| POST | `/admin/models/rollback` | revient au modèle précédent ; journalisé (`model.rollback`) |

Erreurs : `TEST_REQUIRED` (409), `REINDEX_REQUIRED` (409, « réindexation requise » : modèle d'embeddings ou `role: "embedding"`), `NO_PREVIOUS_MODEL` (409), `MODEL_NOT_INSTALLED` (404), `ENGINE_UNREACHABLE` (502).

## ContextBudget (jetons, estimés)

```ts
{
  unit: "tokens"; estimated: boolean;
  window_allocated: number;      // ce que le moteur alloue réellement (ex. 4 096)
  window_max: number | null;     // ce que le modèle sait gérer (ex. 262 144)
  system: number; context: number; passages: number; response_reserved: number;
  free: number;                  // system + context + passages + response_reserved + free = window_allocated
  passages_unsent: number;       // jetons de passages hors fenêtre : jamais envoyés
  passages_unsent_count: number; // nombre estimé de passages concernés
}
```

Composant : `frontend/components/ContextGauge.tsx` (reçoit un `ContextBudget`, sans autre dépendance).

## TestReport

Contrôles : `capabilities`, `context`, `json`, `french`, `citation`, `refusal`, `speed`, chacun `pass | warn | fail`. `passed` = aucun `fail` ; un débit non mesurable est un avertissement. Deux courtes générations seulement (avec preuve, sans preuve). Le test est invalidé si l'empreinte du modèle ou le contexte alloué change.

## Registre et ligne de commande

Fichier `MODELS_REGISTRY_PATH` (défaut `./data/models.json`, ignoré par Git), écrit atomiquement, sans migration : modèle actif, historique, derniers tests. Le fournisseur relit le modèle actif à chaque appel : aucun redémarrage. Le nom exact (`ollama:<modèle>`) est consigné dans chaque exécution.

```
python -m app.models_registry list
python -m app.models_registry test NOM
python -m app.models_registry activate NOM
python -m app.models_registry rollback
```
