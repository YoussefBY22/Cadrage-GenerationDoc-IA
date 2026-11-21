# Lot D3b — Interface : éditeur ancré et validation

## Fait
- `frontend/components/editor/` : `SentenceNode.ts` (nœud TipTap « phrase » : attributs `status`, `sources`, `kind`, `findings` ; bordure verte/orange/rouge ; boutons `[n]` en DOM brut, `textContent` uniquement), `SectionEditor.tsx` (un éditeur par section, TPV, bandeau « preuves insuffisantes »), `convert.ts` (API ↔ TipTap), `ActionBars.tsx` (transitions selon état et rôle, motif obligatoire pour refuser, exports actifs seulement si `approved`), `VersionsPanel.tsx` (liste, restauration, diff), `DeliverableView.tsx`, `RoadmapView.tsx`, `client.ts` (appels livrables/workflow/export), `types.ts`, `i18n.ts`, `editor.css`.
- Pages `app/deliverables/[id]` (sections du gabarit, « Générer la section », sauvegarde → PUT = nouvelle version, versions + restauration + diff, commentaires par section, acquittement par relecteur/admin, exports avec téléchargement) et `app/deliverables/[id]/roadmap` (rang, vague, score, détail par critère avec justification en infobulle, durée, dépendances → PATCH, alerte de cycle, chemin critique).
- Extensions TipTap libres uniquement (document, texte, annuler/rétablir, curseur de dépôt).

## Testé
```
cd frontend && npm run lint  -> aucune erreur
npm test                     -> 4 fichiers, 22 tests passés (12 D3a + 10 D3b)
npm run build                -> réussi (/deliverables/[id] 218 kB, /roadmap 111 kB)
cd backend && ruff check . ; pytest -q -> All checks passed ; 361 passed, 2 skipped
```
Tests D3b : aller-retour API ↔ TipTap sans perte (dont section vide) ; statuts vert/orange/rouge rendus ; TPV ; clic `[n]` → identifiant du passage ; HTML du texte non interprété ; export désactivé hors approved ; motif requis ; rôle consultant sans approuver/refuser ; alerte de cycle + PATCH des scores.

## Limites
- Pas de test de bout en bout dans un vrai navigateur (T3). Le test de saisie clavier dans TipTap n'est pas simulé (jsdom) ; la conversion est testée à part.
- Les statuts sont ceux du dernier rapport serveur : après une frappe, ils restent affichés jusqu'à la sauvegarde (re-vérification côté serveur).
- Les clés de sections viennent d'une table dans `types.ts` (copie des gabarits YAML) : aucun endpoint ne les expose.
- « explain » : le modèle n'a pas de champ dédié ; on affiche valeur par critère, poids et justification.
- Les extensions `@tiptap/extension-document`, `-text` et `@tiptap/extensions` sont importées via les dépendances de `starter-kit` (non déclarées dans `package.json`).

## Écarts aux contrats de 06
Aucun.

## Demandes
- D3a (propriétaire de `vitest.config.ts`) : j'ai **modifié une ligne** (`include`) pour exécuter les tests colocalisés `components/**` et `app/**`. À valider.
- Backend : endpoint `GET /templates/{type}` (clés et titres de sections) ; déclarer les trois paquets TipTap ci-dessus dans `package.json`.

## Pour comprendre
Chaque phrase est une fiche avec un liseré de couleur, comme un correcteur qui passe un surligneur : vert si tout est prouvé, orange s'il doute, rouge s'il a trouvé une erreur. Les petits `[1] [2]` sont des renvois en bas de page : un clic ouvre la pièce justificative. Le bouton d'export est un cachet : tant que le relecteur n'a pas approuvé, il reste grisé.

## 3 questions
1. Pourquoi le statut de la phrase est-il un attribut du nœud et non une partie du contenu sauvegardé ?
2. Pourquoi le serveur re-vérifie-t-il le contenu à chaque sauvegarde plutôt que de croire le client ?
3. Que se passe-t-il pour l'approbation d'un livrable approuvé si on le modifie ?

## Glossaire
TipTap / ProseMirror, nœud (node), NodeView, TPV, diff, quatre yeux.
