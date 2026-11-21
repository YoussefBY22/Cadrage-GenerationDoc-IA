# Comptes rendus de lots

Un fichier `docs/lots/<ID>.md` par lot (≤ 60 lignes), selon `docs/09-plan-execution.md` §1.6. L'orchestrateur fusionne dans `docs/STATUS.md` et le glossaire (`docs/03`, §6).

## Gabarit

```markdown
# Lot <ID> — <titre>
## Fait · ## Testé · ## Limites · ## Écarts aux contrats de 06 · ## Demandes
## Pour comprendre   (5–8 lignes, avec une analogie)
## 3 questions
## Notions pour le glossaire
```

## Index : « Pour comprendre » et « 3 questions » de chaque lot

| Lot | Sujet | Analogie de « Pour comprendre » | Les 3 questions portent sur |
|---|---|---|---|
| [B0](B0.md) | Contrats, routeurs | plan d'immeuble, tableau d'affichage | modèles gelés, dépôt paresseux, TPV d'un refus |
| [B1](B1.md) | Stockage | guichet d'archives, clé d'armoire | filtre `dossier_id` en SQL, force brute vs HNSW, audit en ajout seul |
| [B2](B2.md) | Lecture, sécurité | douanier, détecteur de métaux, sas | signature de fichier, `neutralize` idempotent, signaler plutôt que supprimer |
| [B3](B3.md) | Recherche mixte | bibliothécaire + collègue, RRF | rangs vs scores, titre indexé, oubli d'`invalidate` |
| [B4](B4.md) | Corpus or | examen blanc au corrigé connu | phrase-marqueur, sujets sans preuve, canari |
| [B5](B5.md) | Ingestion, API | chaîne de réception du courrier | passage signalé, 404 vs 403, cache BM25 |
| [C1](C1.md) | Gabarits, prompts | règlement d'archives, enveloppes à cachet | nonce, faux délimiteur, étiquettes P3 |
| [C2](C2.md) | Vérificateur | correcteur qui compare aux notes | `Decimal`, LOW_SUPPORT, ce que mesure le TPV |
| [C3](C3.md) | Score, graphe | note de concours, planning de chantier | poids renormalisés, cycle, vague d'un prérequis |
| [C4](C4.md) | Orchestration | contrôleur de chantier | refus avant appel, constat bloquant, cycle proposé |
| [D1](D1.md) | Validation, comptes | relais à deux témoins | SHA-256 du jeton, 404 inter-dossiers, modification d'un approuvé |
| [D2](D2.md) | Exports | mise sous scellé | contrôle dans le service, empreinte, citations par ordre |
| [D3a](D3a.md) | Interface socle | guichet qui ne décide de rien | jeton mémoire + session, XSS, test statique |
| [D3b](D3b.md) | Éditeur ancré | surligneur vert/orange/rouge | statut hors contenu, re-vérification serveur, approbation modifiée |
| [E1](E1.md) | Entrepôt, ETL | copie propre pour compter, filigrane | fenêtre de 5 min, médiane hors SQL, hypothèse « temps gagné » |
| [E2](E2.md) | Démo, Power BI | fausse activité de 3 mois | `is_demo`, CSV `;` et BOM, pas de Power BI Service |
| [F1](F1.md) | Banc A/B/C/D | jury, faux candidat à 30 % d'erreurs | intervalle de confiance, sécurité bloquante, config A |
| [F2](F2.md) | Entraînement LoRA | préparation de marathon | découpage par document, test d'export, `COMPLETE` en dernier |
| [G1](G1.md) | Livraison hors ligne | bureau sans ligne sortante, valise scellée | `internal: true` + proxy, empreintes avant `pg_restore`, `--no-build --pull never` |
