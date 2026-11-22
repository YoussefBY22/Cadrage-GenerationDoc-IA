# Lot UI — refonte visuelle du front

**Résultat** : interface « Cadrage » (barre latérale anthracite, accent jaune `#FFE600`, police Inter embarquée par `@fontsource/inter`, icônes `lucide-react`), bascule FR/EN, test e2e Playwright du parcours complet, 5 captures dans `docs/img/`.
Aucune marque tierce : le logo est un carré jaune et le mot « Cadrage » ; pied de page « Projet étudiant — non affilié à EY ».

## Où
- Charte : `frontend/app/globals.css` (variables `--yellow`, `--ink`, `--grey`…).
- Libellés : `frontend/lib/i18n/{fr,en}.ts` (même type `Messages`), `t` lit la langue active ; bascule dans `components/ui.tsx`, mémorisée en `localStorage`.
- Pages : tableau de bord (`/dossiers`), dossier (étapes → documents), constats, recherche, éditeur de livrable (couleur de preuve par phrase, panneau de source à droite), feuille de route.

## Test e2e
```powershell
cd frontend
$env:CADRAGE_PYTHON = "<python du backend>"   # dépendances de backend/requirements.lock + reportlab
$env:E2E_API_PORT = "8001"                    # 8001 par défaut
npx playwright install chromium
npm run e2e
```
`e2e/start-api.mjs` génère le corpus synthétique, crée deux comptes (`create_user.py`), lance l'API (`LLM_PROVIDER=demo`, SQLite jetable) ; le front est construit puis servi sur le port 3001. Le test refait : connexion, bascule EN/FR, dossier, import de 3 fichiers, extraction et validation des constats, feuille de route, ToR (6 sections vérifiées), relecture, approbation par un autre compte, exports DOCX et PPTX, et régénère les captures.
Nuit du 22/11 : le port 8001 était occupé par un autre processus (java) ; vérifié avec `E2E_API_PORT=8011`.

## Demandes pour le backend (non faites ici)
1. `GET /dossiers/{id}/deliverables` (id, type, état, version) : le front garde pour l'instant les identifiants du ToR et de la feuille de route dans `localStorage` (`lib/refs.ts`), donc un autre navigateur ne les voit pas.
2. Le fournisseur `demo` produit deux initiatives « Initiative A/B » sans durée : des titres réalistes et `duration_weeks` rendraient la feuille de route plus parlante.
3. Un nom d'affichage dans `GET /auth/me` (le front ne l'affiche pas encore).
4. `GET /dossiers` : ajouter les compteurs (documents, constats, validés) pour éviter un appel par dossier sur le tableau de bord.
