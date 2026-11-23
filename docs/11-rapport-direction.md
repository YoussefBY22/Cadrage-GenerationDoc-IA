# 11 — Rapport à la direction : une nuit de construction assistée

> **Mise à jour du 23/11/2026, pour un manager.**
> - **Fait** : les trois éléments du sujet sont désormais reliés dans l'outil : constats d'audit, priorités de la
>   société validées par un relecteur, projets existants. Sur un audit fictif, le modèle local relie chaque action
>   à la bonne priorité. Un livrable sans preuve valide ne peut plus être approuvé ni exporté.
> - **Mesuré** : 0 % de réponses sans preuve grâce au filtre de pertinence (seuil à recalibrer sur données réelles) ;
>   une tentative de manipulation sur cinq suivie par le modèle, bloquée à l'approbation.
> - **Pas encore** : saisie des décisions humaines (budget, profils, calendrier), modèle spécialisé (entraînement),
>   lecture des images, espace client.


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
| Erreurs injectées détectées | 23/23 cas construits, 8 types d'erreur (ne couvrait ni nombres en lettres, ni fourchettes, ni sens) |
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
Total de la nuit : **88 pts de la fenêtre de 5 h** (59 + 29 sur deux fenêtres) et **15 pts de l'hebdomadaire** (64 → 79 %). Un lot Sonnet coûte 3 à 4 pts ; l'architecte Opus ~10 pts à lui seul. Le lot le plus lourd est la vague V3 (sessions réutilisées donc contexte déjà chargé). Une pause volontaire à 93 % a évité toute interruption en plein travail. La rédaction de ce rapport (R3) a coûté environ 2 pts de 5 h et moins de 1 pt hebdomadaire (relevé de l'orchestrateur : 32 → 34 % et 79 → 79 %). Il reste **21 % de l'hebdomadaire**, gardés pour les lots T1 à T6 avec l'utilisateur.

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

---

# Nuit 2 — passage au réel (22/11/2026, ~01 h à 05 h)

*Sources : journal de l'orchestrateur, `docs/lots/` T1, T2, UI, EN, T4, T6.*

## Ce qui a changé
Six sessions en parallèle, sur des fichiers distincts, ont fait tourner pour la première fois **un vrai modèle, une vraie base, Docker, un navigateur, LibreOffice et Power BI**.
- **Correction du 22/11 au soir** : les chiffres de génération qui suivent ont pu être mesurés sur des invites tronquées (fenêtre de 4 096 jetons), ils sont à refaire.
- **Modèle local réel** : qwen3:4b et bge-m3 (Ollama) sur un PC à 4 Go de VRAM. Par section : **18,2 s** (p50), 23,1 s (p95), 3,1 Go de VRAM ; rappel@10 **1,000** (31 sections, 1 institution). Un réglage (`num_gpu=99`) a réduit la latence de 25 % et les faux refus de 60 à 10 % (une passe : bruit de ±1–2 sections).
- **PostgreSQL + pgvector** et entrepôt : exécutés sans bug ; le rôle de lecture `bi_reader` n'accède qu'à `dw`.
- **Corpus réel** : **103 documents CC BY**, 3 105 exemples d'entraînement (jeu **rejeté** le 22/11/2026 après lecture : réponses presque toutes recopiées des passages (2 061 sur 2 067), questions faites de mots-clés, 83 % en anglais, aucune feuille de route ni TdR ni cahier des charges), 34 questions de test rédigées par une IA et non relues par un humain, licences et SHA-256 tracés.
- **Interface** refaite (jaune et anthracite, sans marque), **FR/EN**, test navigateur de bout en bout ; **livrables en anglais** ; Power BI (thème, projet PBIP, CSV) ; export PDF par LibreOffice.
- **Hypothèses H1 à H7** (sur site, GPU 24 Go / PC 4 Go, formats, trames, données publiques, consultant + manager, seuils de réussite) écrites au cahier des charges, à valider avec l'entreprise.

## Contrôles
Backend **432 passés, 5 sautés** ; PostgreSQL réel 4 passés ; entraînement 33 ; interface lint, 22 tests, build. Le build Docker du front avait échoué (lockfile) et 4 tests de scripts échouent sous Windows (shim WSL) : corrigés ou notés par les lots.

## Consommation
~44 pts de la fenêtre de 5 h et ~8 pts de l'hebdomadaire pour les six lots (de 78 % à 87 % de l'hebdo à 04 h 05).

## Limites restantes
- **L'entraînement LoRA n'a pas eu lieu** (T5) : le modèle C n'existe pas.
- Le TPV réel (1,000) ne discrimine pas ; les vrais signaux sont les refus. Évaluation réduite à 31 sections : la B complète prend ≈ 1 h.
- Corpus réel peu francophone (17 %) ; réponses d'entraînement extractives ; jeu or petit (intervalle large).
- Le projet Power BI n'a pas été ouvert dans Desktop ; les valeurs du tableau de bord sont inventées.
- Défender a bloqué `soffice.bin` dans Documents : aucun réglage de sécurité modifié ; profil et dossier temporaires dans le lot Q.

## Suite
T5 (LoRA réel, C contre B), B complète, ouverture du PBIP, source francophone, validation des hypothèses avec l'entreprise.
