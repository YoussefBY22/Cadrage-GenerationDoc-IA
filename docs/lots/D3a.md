# Lot D3a — Interface : socle, dossiers, documents, constats

## Fait
- `frontend/` : Next.js 15 (App Router, TypeScript strict), React 19. Dépendances TipTap (`@tiptap/react`, `starter-kit`, `pm`) installées pour D3b, non utilisées ici.
- `lib/api-types.ts` (types à la main depuis 06), `lib/api.ts` (client fetch, `ApiError{status,code,message}`, jeton en mémoire + `sessionStorage`, `NEXT_PUBLIC_API_URL` défaut `http://localhost:8000`, 401 → jeton effacé), `lib/useGuard.ts` (401 → `/login`), `lib/i18n/fr.ts` (type `Messages` prêt pour `en.ts`).
- Pages : `/login`, `/dossiers` (liste + création), `/dossiers/[id]` (documents, glisser-déposer, messages 409/413/415, badge d'alerte d'injection), `/dossiers/[id]/search`, `/dossiers/[id]/findings` (cocher = valider, corriger, sources `[n]` → `SourcePanel` via `GET /chunks/{id}`).
- Tout texte de l'API est rendu en texte React ; aucune police ou URL externe ; `NEXT_TELEMETRY_DISABLED=1` posé dans `next.config.mjs` (portable Windows) et `.env.example`.

## Testé
```
cd frontend && npm run lint  -> aucune erreur
npm test                     -> 3 fichiers, 12 tests passés (vitest, fetch simulé)
npm run build                -> réussi (7 routes), sans réseau
cd backend && ruff check . ; pytest -q -> All checks passed ; 350 passed, 2 skipped
```
Tests : client API (login/Bearer, 401, 404, 409, multipart, erreur non JSON) ; constats (valider, corriger, ouverture du panneau) ; panneau source (HTML non interprété, alerte, page/section, 404) ; recherche statique de `dangerouslySetInnerHTML`/`innerHTML` et d'URL externes.

## Limites
- Le badge d'alerte n'apparaît que pour les documents importés pendant la session : `GET /dossiers/{id}/documents` ne renvoie pas le nombre d'alertes.
- Pas de garde de route côté serveur : une 401 redirige vers `/login`. En mode `dev` du serveur, la connexion n'est pas nécessaire.
- Pas de test de navigateur réel (Playwright reporté à T3).
- Recherche : requête unique (`texts` à 1 élément), k = 10.

## Écarts aux contrats de 06
Aucun. `next-env.d.ts` est versionné (sinon `next build` à froid échoue) et `globals.d.ts` déclare `*.css`.

## Demandes
- G1 : `frontend/Dockerfile` ; CORS côté API si le front et l'API ont des origines différentes (`main.py`, B0).
- Backend : ajouter `alerts` (ou `injection_flags` par document) à `GET /dossiers/{id}/documents`.

## Pour comprendre
Le front est un guichet : il ne décide de rien, il montre ce que l'API renvoie et transmet les actions. Le client API est le guichetier unique : il ajoute le badge (jeton), traduit les refus en erreurs typées et efface le badge quand il est périmé. Chaque texte venu du serveur est posé comme une étiquette, jamais interprété comme du code.

## 3 questions
1. Pourquoi garder le jeton en mémoire ET en `sessionStorage` ?
2. Que se passerait-il avec `dangerouslySetInnerHTML` sur un passage piégé ?
3. Pourquoi le test d'absence de `dangerouslySetInnerHTML` cherche-t-il dans le code source ?

## Glossaire
App Router, composant client, jeton porteur (Bearer), XSS, vitest, jsdom.
