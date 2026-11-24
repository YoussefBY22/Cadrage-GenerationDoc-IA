# Lot AXES — Feuille de route par axes (24/11/2026)

## Problème

Sur un vrai rapport (rapport spécial 17/2022 de la Cour des comptes européenne, ~100 pages), l'extraction donne
55 à 93 constats. La feuille de route les envoyait tous au modèle **en une seule question** (~4 500 à 5 900
jetons) : la fenêtre de 4 096 jetons était dépassée et l'application refusait (`CONTEXT_FULL`). Passer à 8 192
jetons faisait tenir la question, mais le modèle, à moitié sur le processeur, dépassait 5 min et était coupé.
Les TdR avaient le même défaut : chaque section recevait **tous** les constats du dossier (17 000 caractères).

## Ce que font les cabinets

Les sources publiques consultées (McKinsey, guide PEFA de la Banque mondiale, cabinets de conseil français)
découpent une feuille de route sur deux dimensions :

- des **axes** (chantiers, *workstreams*) : gouvernance, processus, systèmes d'information, données, RH… ;
- des **horizons** : gains rapides, fondations, transformation de long terme, ordonnés selon la valeur, la
  faisabilité, les dépendances et la capacité, en commençant par les bases (*basics first*).

Aucune méthode propre à EY n'est publique.

## Changements

| Étape | Qui | Détail |
|---|---|---|
| 1. Doublons | code (`app/roadmap/axes.py`) | constats quasi identiques (≥ 85 % de mots communs) fusionnés ; le doublon suit son représentant |
| 2. Axes | modèle, par lots de 25 | les axes nouveaux sont déclarés une fois (A1 : titre), puis une ligne (constat, A…) par constat, selon son sens ; les axes déjà créés sont rappelés par identifiant |
| 3. Initiatives | modèle, axe par axe | au plus 8 constats et 4 initiatives par appel (réponse jamais tronquée) ; un axe trop gros est découpé ; une partie ratée est signalée (« constats à reprendre ») sans effacer les autres |
| 4. Fusion | code | même titre proposé deux fois : une seule initiative ; dépendances résolues entre tous les axes |
| 5. Classement, vagues | code (inchangé) | score, rang, vagues, chemin critique |
| TdR / CdC | code (`services/generation.py`) | une section d'une initiative ne reçoit que **ses** constats, au plus 30 % de la fenêtre ; le surplus est compté (`findings_not_sent`) |
| Interface | `RoadmapView.tsx` | tableau **axes × vagues** ; axe affiché sous chaque initiative |

Jusqu'à 8 constats distincts, rien ne change : un seul appel, l'axe vient du thème donné à l'extraction.

## Mesures réelles (cadrage-4b-lora, GTX 1650, fenêtre 4 096)

| | Avant | Après |
|---|---|---|
| Feuille de route sur 55 constats | refusée (`CONTEXT_FULL`) ; 8 192 jetons : coupée après 604 s | **produite** en 1 651 s (~27 min) : 3 appels « axes » (30-60 s), 9 appels « initiatives » (2-4 min) |
| Initiatives | — | 12, sur 2 axes (Conformité, Données) |
| Parties ratées | — | 1 sur 9 (réponse trop longue malgré la limite), signalée |
| Constats sans initiative | — | 6 sur 55 (signalés par le contrôle de cohérence) |
| TdR « contexte » | 400 d'Ollama (prompt > fenêtre) ; avant ce lot, TPV 0,7 sur 13 constats | **TPV 1,0** en 70 s |

## Limites

- Le modèle entraîné n'a jamais appris à trouver des axes : il en propose 2 au lieu de 3 à 7, et nomme parfois
  une initiative du nom de l'axe (« Données »). À ajouter au prochain jeu d'entraînement.
- Lent sur un GPU de 4 Go (~27 min pour 55 constats) ; une partie sur 9 échoue encore.
- Les horizons restent des vagues numérotées : pas encore de libellé « 0-6 mois / 6-12 mois / 12-24 mois »
  (il faut une date de départ et des durées, saisies par le consultant).

## Tests

`pytest` : 725 réussis, 4 ignorés (PostgreSQL absent), dont 7 nouveaux dans `tests/roadmap/test_axes.py`
(doublons, lots, noms d'axes, parcours complet, partie ratée, TdR filtrée). `vitest` : 12 réussis (dont le
tableau axes × vagues) ; `tsc` et `eslint` propres.
