# 18 — Rapport technique détaillé (21 au 23/11/2026)

> Lecteur : technique. Complète [`12-journal-orchestration.md`](12-journal-orchestration.md), qui couvre surtout la
> nuit 1, et [`11-rapport-direction.md`](11-rapport-direction.md), qui est la synthèse pour un manager. Sources : PR
> du dépôt, liste des sessions de l'application, journal de l'orchestrateur. Horaires en heure de Tunis,
> approximatifs.

## 1. Organisation

- **Orchestrateur** : une session Opus, qui planifie, écrit les consignes, audite chaque rendu (code, rendu, vrai
  modèle), fusionne sur accord et tient ce journal.
- **Développeurs** : sessions Sonnet, chacune dans son dossier Git isolé (worktree), une branche et une PR.
- **Règles constantes** : aucune donnée client ; commits au seul nom de YoussefBY22 ; aucune fusion sans accord
  explicite ; aucun entraînement avant validation des données ; aucun calcul GPU dans les sessions (seul
  l'orchestrateur lance le vrai modèle, en surveillant la température).

## 2. Combien de sessions, et qui a fait quoi

**25 sessions de développement** dans ce projet, plus l'orchestrateur et une session cloud de démarrage (phase A).
Plusieurs sessions ont enchaîné plusieurs lots : il y a eu plus de lots que de sessions.

### Nuit 1 (21/11, 21 h 50 → 22/11, 01 h) : construire tout le produit, avec un faux modèle

| Session | Lots | Contenu | Résultat |
|---|---|---|---|
| Phase A (cloud) | A | socle FastAPI, interface `LLMProvider`, faux modèle, garde-fou réseau | 22 tests |
| Architecte (Opus) | — | docs 05 à 09, plan de 18 lots en 6 vagues | +1 234 lignes de documentation |
| dev-b0 | B0, G1 | contrats, socle ; livraison hors ligne | fusionnés |
| dev-b1 | B1, E2 | stockage abstrait ; Power BI | fusionnés |
| dev-b2 | B2 | lecture PDF/DOCX/PPTX, détecteur d'injection | fusionné |
| dev-b3 | B3 | recherche BM25 + vecteurs + RRF | fusionné |
| dev-b4 | B4, F2 | corpus d'évaluation ; jeu d'entraînement (simulation) | fusionnés |
| dev-b5 | B5, D3b | ingestion, API ; éditeur ancré | fusionnés |
| dev-c1 | C1, D2 | gabarits et prompts ; exports DOCX/PPTX/PDF | fusionnés |
| dev-c2 | C2, R1 | vérificateur ; revue réelle | fusionnés |
| dev-c3 | C3, D3a, R3 | priorisation et graphe ; interface ; rapports | fusionnés |
| dev-c4 | C4, F1 | génération « preuve d'abord » ; banc d'évaluation | fusionnés |

Bilan : 19 lots, **397 tests** verts, environ 2 h 50 d'orchestration.

### Nuit 2 et 22/11 : passage au réel

| Session | Contenu | Résultat |
|---|---|---|
| T1 Postgres | PostgreSQL + pgvector réels, entrepôt | fusionné |
| T2 Ollama | qwen3:4b et bge-m3 réels, première évaluation | fusionné ; chiffres remesurés depuis (§4) |
| UI | interface style EY, Playwright | fusionné |
| gen-en | livrables en anglais ; lots Q et Q2 (porte de pertinence) | fusionnés |
| T4 corpus | 103 documents publics, 3 105 exemples | **jeu rejeté** après lecture (réponses recopiées, 83 % anglais) |
| T6 BI | thème Power BI, PDF LibreOffice | fusionné |
| T5 entraînement | premier essai LoRA sur GPU | **échec** : Ollama refuse les adaptateurs LoRA ; arrêtée |
| Référentiels | ISO 29148, Banque mondiale, COBIT dans les gabarits | #2, fusionnée le 23/11 |
| Power BI refonte | tableau de bord par acteur, proposition client | #4, #6, #13 fusionnées |
| Refus et temps gagné | sous-session de la précédente | interrompue par l'utilisateur, travail sauvegardé |

### 22/11 soir et 23/11 : la cible du sujet EY

| Session | PR | Contenu | Allers-retours d'audit |
|---|---|---|---|
| Orchestrateur | #7 | fenêtre de contexte : 3 892 mots envoyés, 2 050 jetons lus sans erreur → refus explicite | — |
| Orchestrateur | #8, #9, #10 | cahier v0.2 ; nombres en lettres ; chiffres publics corrigés | — |
| Lot A cœur métier | #12 | rôles de documents, priorités, projets, 8 contrôles de cohérence | 2 : priorités jamais reliées et scores égaux en réel, puis 4 écarts mineurs |
| Lot C1 modèles | #11 | registre de modèles, page Modèles | 2 : nom de modèle journalisé faux, débit faux, mode démo |
| Orchestrateur | #14 | verrou d'approbation (faille signalée par la session Power BI) | 26 tests rouges sur main avant correction |
| Lot B | #18 | décisions humaines, fiche de contexte, chat, gabarits par type | 2 : décisions ignorées par le modèle, CI rouge |
| Jeu de données | #16 (ouverte) | sources publiques à licence prouvée, 25 exemples | audité, faiblesses listées (§5) |
| Orchestrateur | #15, #17 | remesure ; documentation | — |

## 3. Ce que l'audit par l'orchestrateur a changé

Les tests verts des sessions ne suffisaient pas. Chaque lot a été rejoué sur qwen3:4b avec un audit fictif :

| Défaut trouvé seulement en réel ou en lecture | Corrigé dans |
|---|---|
| Fenêtre de 4 096 jetons tronquée en silence | #7 |
| 0 initiative sur 5 reliée à une priorité, 5 scores égaux | #12 |
| Dates inventées, Gantt à 4 semaines par défaut | #12 |
| Source inexistante acquittable puis effacée à l'export | #14 |
| Nom de modèle journalisé faux après changement d'actif | #11 |
| TdR « Profil » recopiant les constats ; puis décisions ignorées | #18 |
| Étiquette COBIT identique sur 5 initiatives | #2 (retirée) |

## 4. Mesures réelles (23/11, qwen3:4b, GTX 1650 4 Go)

Détail : [`lots/R2.md`](lots/R2.md).

- Refus manqués : 0 % avec la porte de pertinence, 70 % sans elle. Faux refus : 0 %.
- Citations valides et chiffres fidèles : 100 %. Rappel@10 : 1,0.
- Attaques par consigne cachée : 1 sur 5 suivie (signalée, non approuvable).
- Feuille de route : 5 initiatives sur 5 reliées à la bonne priorité.
- Latence par section : 21,7 s (p50). GPU : 89 à 91 °C en charge continue.

## 5. Entraînement : où on en est (au 23/11 après-midi ; suite dans [`19-entrainement-et-tests-reels.md`](19-entrainement-et-tests-reels.md))

- Aucun entraînement n'a abouti.
- Chaîne d'export (fusion LoRA, GGUF, import Ollama) prouvée sur Ollama 0.40.16 puis 0.40.17.
- Données :
  - pilote v2 de 30 exemples, relu par l'orchestrateur à la demande de l'utilisateur (24 acceptés, 6 corrigés) ;
  - pilote v3 de 25 exemples (#16).
  Le v3 est bon pour la feuille de route et l'extraction de constats, faible pour les TdR (simples extraits de
  CCTP) et pour les « divergences » (simple reprise des deux textes).

## 6. Consommation (forfait Pro)

| Moment | Fenêtre 5 h | Hebdomadaire | Contexte |
|---|---|---|---|
| 21/11 21 h 58 | 34 % | 64 % | avant l'orchestration |
| 22/11 00 h 54 | 32 % (après reset) | 79 % | fin de la nuit 1 |
| 22/11 04 h 05 | 78 % | 87 % | nuit 2, 6 lots finis |
| 22/11 ~20 h 30 | 13 % | 19 % (nouvelle semaine) | demande cible produit |
| 22/11 ~22 h 30 | 100 % | 33 % | audits et 3 sessions ; arrêt jusqu'au reset |
| 23/11 09 h 40 | 8 % | 35 % | reprise |
| 23/11 ~11 h 30 | 47 % | 42 % | fusions, PR 2, remesure |
| 23/11 ~14 h 40 | 100 % puis reset | 50 % | lot B coupé par la limite, relancé |

Ce qui coûte le plus : les sessions réutilisées (contexte déjà chargé) et les audits réels qui renvoient des
corrections. Ce qui a économisé : briefs écrits une fois, sessions Sonnet pour le code, Opus seulement pour
l'orchestration.

## 7. Incidents

- Quota de 5 h épuisé deux fois, sans perte de travail.
- Un commit de mise à jour créé par GitHub avec l'adresse principale du compte : ne plus utiliser « Update branch ».
- Archivage d'une session ayant entraîné celui de sa sous-session interrompue : dossier intact, copie de sécurité faite.
- Fusions et lancement de session parfois refusés par le mode automatique ou en contrôle à distance : faits sur
  accord explicite, ou par l'orchestrateur lui-même.
- Test d'interface instable (« window is not defined ») : passé à la relance, à stabiliser.
