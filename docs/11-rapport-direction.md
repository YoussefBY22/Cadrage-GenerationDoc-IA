# 11 — Rapport à la direction : une nuit de construction assistée

*Projet PFE « Assistant IA local de cadrage » · nuit du 21 au 22/11/2026 · sources : journal d'orchestration (`docs/12`), `docs/STATUS.md`, comptes rendus `docs/lots/`. Tout chiffre non mesuré est signalé.*

## 1. Le projet en trois lignes
Les consultants rédigent sans cesse les mêmes livrables (feuilles de route, termes de référence, cahiers des charges) à partir de diagnostics confidentiels. L'outil prépare un **premier jet cité et vérifié**, 100 % **sur le serveur du client** (modèle ouvert, sans API ni cloud) ; le consultant relit, corrige et valide à deux personnes, puis exporte en Word, PowerPoint ou PDF. Sujet : *Stages & PFE Book 2026-2027*, p. 92, Réf. #TST 11.

## 2. L'approche : un chef d'orchestre et des exécutants
```
Orchestrateur (Opus 5.5)  ──►  Architecte (Opus 5.5) : 5 documents + plan de 19 lots
        │                              │
        └── vagues parallèles de développeurs (Sonnet 5.5, un lot chacun)
   V0 : 1 lot · V1 : 4 · V2 : 4 · V3 : 4 · F1 seul · V4 : 3 · V5 : 2 · puis revue (R1), documentation (R2), rapport (R3)
```
Chaque lot possède une liste de fichiers (aucun conflit de fusion), lit son brief, teste, écrit un compte rendu et pousse. L'orchestrateur fusionne après chaque vague et relance `ruff` et `pytest` lui-même.

## 3. Ce qui est livré
- **Backend** FastAPI : ingestion PDF/DOCX/PPTX/TXT, recherche mixte (mots-clés + sens), génération « preuve d'abord », vérificateur de citations et de chiffres, priorisation et chemin critique, circuit de validation à deux personnes avec audit, exports DOCX/PPTX/PDF.
- **Interface** Next.js : dossiers, documents, constats, éditeur où chaque phrase est colorée selon sa preuve, versions, feuille de route.
- **Entrepôt** en étoile (10 dimensions, 5 faits, 7 vues, 14 indicateurs) et pas-à-pas Power BI ; **banc d'évaluation** A/B/C/D ; **scripts d'entraînement** LoRA sûrs ; **livraison hors ligne** (Docker, sauvegarde, restauration).
- Dépôt : 312 fichiers suivis, environ 13 700 lignes Python, 2 300 lignes TypeScript, 40 documents Markdown.

## 4. Chiffres clés (avec un faux modèle : ils valident la mécanique, pas un vrai modèle)
| Mesure | Résultat |
|---|---|
| Tests automatiques | **397** backend + 22 entraînement + 22 interface ; 2 sautés (PostgreSQL, LibreOffice) ; lint vert |
| Rappel@10 de la recherche | **1,000 (30/30)** sur 30 requêtes, 3 institutions fictives |
| Erreurs injectées détectées | **23/23 (100 %)**, 8 types d'erreur |
| Attaques par injection | 14 détectées, 0 faux positif sur 25 phrases normales |
| Parcours de démonstration complet (10 étapes, import → ToR → approbation → export) | **1,9 s**, ToR de 6 sections, TPV 1,00, 28 entrées d'audit |
| Revue d'intégration (R1) | **5 bugs** trouvés et corrigés, avec tests |

## 5. Consommation (forfait Pro, points de pourcentage)
```
Architecte Opus+mise en place ████████████ 12      V3 (C4, D1, D2, E1) █████████████████ 17
V1 (B1–B4)                    █████████████ 13      V4 (D3a, E2, F2)    █████████████ 13
V2 (B5, C1–C3)                ██████████ 10         R1 + R2             █████████ 9
V5 (D3b, G1)                  ███████ 7             F1                  ████ 4      B0 ███ 3
```
Total de la nuit : **88 pts de la fenêtre de 5 h** (59 + 29 sur deux fenêtres) et **15 pts de l'hebdomadaire** (64 → 79 %). Un lot Sonnet coûte 3 à 4 pts ; l'architecte Opus ~10 pts à lui seul. Le lot le plus lourd est la vague V3 (sessions réutilisées donc contexte déjà chargé). Une pause volontaire à 93 % a évité toute interruption en plein travail. Le coût de la rédaction de ce rapport (R3) est non mesuré.

## 6. Risques et limites
- **Aucun vrai modèle, aucune base PostgreSQL, aucun Docker, aucun navigateur n'a tourné** : tous les chiffres viennent d'un faux modèle et de SQLite. La qualité rédactionnelle réelle reste inconnue.
- Le vérificateur prouve que la phrase s'appuie sur ses sources, **pas qu'elle est vraie**.
- Licences et noms de modèles écrits de mémoire (« à vérifier » dans `08`) ; hypothèse de 30 min gagnées par section à valider.
- Le chemin PostgreSQL, l'export PDF, les scripts de livraison et l'entraînement réel sont codés mais **jamais exécutés**.

## 7. Demain (avec l'utilisateur, réseau ou Docker)
| Lot | Contenu |
|---|---|
| T1 | PostgreSQL + pgvector, migrations, entrepôt, tests `-m postgres` |
| T2 | Vérifier les licences, installer Ollama et les modèles, première évaluation réelle |
| T3 | Parcours complet dans un vrai navigateur (Playwright) |
| T4 | Corpus public (licences notées) et jeu d'entraînement |
| T5 | Entraînement LoRA réel (Colab puis PC la nuit), comparaison C contre B |
| T6 | LibreOffice (PDF), Power BI Desktop, images Docker |

> **Encadré — Sans orchestrateur, comment l'étudiant aurait procédé** *(estimation, non mesurée)*
> Seul, un étudiant ferait ce travail **séquentiellement**, à raison de ~6 h utiles par jour : (1) lire le sujet et cadrer, 2–3 j ; (2) choisir l'architecture et écrire les contrats, 3–4 j ; (3) socle, stockage, import et recherche, 8–10 j ; (4) génération, vérificateur, priorisation, 8–10 j ; (5) validation, comptes, exports, 6–8 j ; (6) interface et éditeur, 8–10 j ; (7) entrepôt et Power BI, 4–5 j ; (8) évaluation, entraînement, livraison, 6–8 j ; (9) tests et documentation tout au long, +20 %. Total estimé : **environ 8 à 10 semaines à temps plein (≈ 250–350 h)**, contre ~3 h d'horloge pour cette nuit, plus la relecture humaine, qui reste nécessaire. Le goulot n'est pas la frappe mais les décisions : l'orchestration les a prises en amont (plan, propriété des fichiers) pour paralléliser. Le temps de compréhension et de validation par l'étudiant n'est pas supprimé : il est déplacé vers la relecture.
