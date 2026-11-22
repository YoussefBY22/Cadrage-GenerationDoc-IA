# 15 — Architecture cible et matrice des demandes (v0.2)

> Proposition du 22/11/2026, **à valider**. Elle complète le [cahier des charges](01-cahier-des-charges.md).
> « Existe » veut dire : lu dans le code de `main` (fb2bfeb). Le reste est à construire ou non vérifié.

## 1. Où en est-on face au sujet

| Élément du sujet | État | Ce qui manque |
|---|---|---|
| Documents fournis | partiel | rôle du document, lecture intégrale affichée, OCR, tableaux, graphiques |
| Constats d'un diagnostic | partiel | priorité au diagnostic, couverture de tous les passages, contradictions |
| Priorités institutionnelles | **absent** | saisie ou extraction, rang, validation, lien avec chaque initiative |
| Dépendances entre projets | **faible** | projets existants et en cours, types de dépendance, durées |
| Cohérence entre les trois | **absent** | chaîne complète et contrôles croisés (§3) |
| Feuille de route priorisée | partiel | priorités, projets, calendrier calculé, égalités de score |
| Termes de référence | partiel | décisions humaines (budget, profils, délais), variantes |
| Cahier des charges adapté au contexte | **faible** | types de projet, questionnaire, chat, validation par section |
| Sources visibles | existe | jauge de contexte, passages non lus signalés |
| Révision humaine | existe | niveau sémantique explicite, validation par section |

## 2. Vocabulaire

- **Diagnostic / rapport d'audit** : ce qui ne va pas, avec des preuves.
- **Feuille de route** : quoi faire, dans quel ordre, pourquoi.
- **Termes de référence (TdR)** : le document qui cadre une **mission à confier** (contexte, objectifs, étendue, livrables, profils, délais, évaluation). Ce n'est pas une liste de références.
- **Cahier des charges (CdC)** : ce que la **solution ou la prestation** doit satisfaire, et comment on la réceptionne.

## 3. Chaîne métier (FR-19)

```
document → constat → objectif → initiative → priorité calculée → place au calendrier → TdR / CdC
                        ↑            ↑
      priorité institutionnelle   projet existant (dépendance)
```

Chaque initiative répond à sept questions : pourquoi, quel constat, quel objectif, pourquoi prioritaire, dépend de quoi, quel résultat, comment le mesurer.

Contrôles déterministes, sans LLM :

1. constat majeur sans initiative ;
2. initiative sans constat ou sans priorité institutionnelle ;
3. priorité institutionnelle sans initiative ;
4. initiative en doublon d'un projet en cours ;
5. dépendance cyclique, ou initiative placée avant son prérequis ;
6. initiative plus prioritaire que son prérequis : signaler la priorité héritée ;
7. égalité de score : départage explicite, jamais l'ordre du modèle ;
8. durée absente : ordre seulement, aucune date inventée ;
9. TdR ou CdC qui contredit l'initiative dont il découle.

Processus en six étapes, chacune validée par un humain : constats → priorités → projets existants → initiatives → priorisation et dépendances → calendrier.

## 4. Trois natures d'énoncé

| Nature | Origine | Règle |
|---|---|---|
| **Fait sourcé** | passage d'un document | citation vérifiée |
| **Proposition IA justifiée** | raisonnement à partir de faits | marquée, jamais comptée comme fait, acceptée ou refusée par un humain |
| **Décision humaine** | formulaire ou chat confirmé | auteur et date, **citable** comme un document |

Sans cette distinction, un TdR est impossible : budget, profils et planning ne figurent pas dans un diagnostic.

Trois niveaux de vérification : la citation **existe** (code) ; elle est **fidèle**, chiffres et nuances (code, puis humain) ; elle **justifie** la phrase (aide sémantique non bloquante, puis humain).

## 5. Documents

| Rôle | Traitement |
|---|---|
| Diagnostic / audit, sans limite de nombre | lu **en entier, par lots, en premier** ; place réservée dans la recherche |
| Stratégie / priorités institutionnelles | extraction proposée, puis validation |
| Portefeuille de projets | projets, états, durées, dépendances |
| Autre document | contexte, preuves complémentaires |
| Trame | forme seulement, jamais source de faits |

- Un poids plus fort ne masque pas une contradiction : elle est affichée et tranchée par un humain.
- Un nouveau rapport ne remplace pas l'ancien en silence : versions et dates conservées.
- Couverture affichée : passages lus / total, pages sans texte, images et graphiques non interprétés.
- Scans : OCR local. Graphiques : modèle de vision local optionnel, valeurs extraites **à confirmer**. `qwen3:4b` ne voit pas les images.

## 6. Contexte, chat et gabarits

- Fiche de contexte : secteur, taille, pays, langue, type de projet, périmètre, contraintes, budget, délais, parties prenantes.
- **Formulaire court et chat** : le chat pose les questions manquantes, propose des champs, et rien n'entre dans la fiche sans confirmation. L'historique du chat n'est pas une source.
- Un tronc commun, plus des modules par type : logiciel et SI ; données et IA ; infrastructure et travaux ; fournitures et équipements ; services et externalisation ; étude, conseil et assistance ; organisation et conduite du changement ; formation ; autre (trame fournie).
- Plusieurs modules peuvent se combiner. Génération et validation **section par section**.
- Le chat applique les mêmes protections contre les consignes cachées et n'a aucun accès réseau.

## 7. Modèle, contexte et limites

| Limite | Dépend de |
|---|---|
| contexte maximal théorique | modèle (`qwen3:4b` : 262 144 jetons) |
| contexte réellement alloué | moteur, réglage et mémoire vidéo (mesuré : 4 096 sur 4 Go) |
| vitesse | matériel, quantification, longueur |
| images | capacités du modèle |
| taille et format d'un fichier | application (25 Mo ; PDF, DOCX, PPTX, texte) |

À saturation : refus explicite du moteur, découpage en lots, résumé validé. Jamais de coupe silencieuse. L'interface montre la part du système, du contexte, des passages, de la réponse et les passages non envoyés.

Changer de modèle :

1. le déposer dans le moteur local (fichier GGUF, ou dossier safetensors) ;
2. le choisir dans l'interface ou en ligne de commande ;
3. test automatique : capacités, contexte réel, JSON, français, refus, citations, débit ;
4. banc d'essai contre le modèle en service ;
5. activation humaine, retour arrière en un geste.

- Un changement de modèle de génération **n'exige pas d'entraînement** : instructions et gabarits versionnés suffisent pour démarrer.
- Un LoRA est propre à sa base : autre base, nouvel entraînement et nouvelle évaluation.
- Un changement de modèle d'embeddings exige une **réindexation**.
- Ollama convient au poste et au prototype. Un moteur multi-utilisateur (vLLM, par exemple) se branche derrière la même interface, avec file de tâches.
- RAG et LLM sont complémentaires : la recherche trouve, le modèle local rédige.

## 8. Studio d'entraînement

- Local d'abord : modèle de base au format safetensors, jeu versionné et **validé**, intensité (pauses **dans la boucle**), estimation après un palier court.
- Écran : étape en langage simple, dépliable vers commande et journal ; progression ; courbes de température, GPU, mémoire et perte ; arrêt propre, reprise ; tests avant et après.
- Commandes choisies dans une liste fermée. Pas de terminal libre dans une application qui contient des données client.
- Export prouvé **avant** l'entraînement long : fusion, conversion GGUF, création Ollama, même chaîne pour la base et l'adapté.
- Colab, données publiques uniquement : l'application prépare le carnet et le paquet, l'utilisateur lance, l'application relit les résultats exportés. La [FAQ de Colab](https://research.google.com/colaboratory/faq.html) interdit sur l'offre gratuite le pilotage à distance et le contournement de l'interface du carnet, ne publie pas les quotas et limite une session à 12 h au plus. **Pas de quota restant affiché.**
- Aucun entraînement sur données client sans accord écrit, et jamais hors de son serveur.

Dossier produit à chaque entraînement : origine et licence des données, empreintes, auteur et relecteur de chaque exemple, séparation des tests, modèle de base et révision, prompt exact, paramètres, matériel, courbes, incidents, métriques avant et après, échecs lus, décision.

Jeu cible (effectifs à valider) : extraction 50, diagnostic 40, feuille de route 40, TdR 30, CdC 30, refus 30, contradictions 20, avec conservation des nuances (« souvent », « pourraient »). Test séparé par source.

## 9. Utilisateurs et déploiement

- À terme le **client est l'utilisateur principal** : il dépose, répond, suit, commente.
- Le sujet impose que **le consultant reste responsable de la validation**. Le client peut donc tout préparer, mais un consultant nommé approuve.
- Par défaut une installation **sur site par client**, conforme à H1. Une plateforme centrale privée est une option ultérieure, qui change H1 et exige une isolation renforcée.
- Pièces et base sont aujourd'hui en clair : chiffrement du disque obligatoire, chiffrement applicatif à étudier.
- À prévoir : sauvegarde testée, suppression et durée de conservation par client, mise à jour hors ligne, reprise des tâches longues, journal des accès.
- Tableau de bord du cabinet conservé. Tableau de bord client séparé, un jeu de données par client, propositions validées seulement.
- Domaine financier (lois par pays, calculs) : lot ultérieur, avec calculs par code, textes datés et expert responsable.

## 10. Matrice des demandes

| Demande | Objet | Exigences | Lot |
|---|---|---|---|
| R01, R03 | conformité, cohérence des trois éléments | FR-19 à FR-21 | A |
| R02 | LLM local et RAG | D1, D2, D4, NFR-04 | existe |
| R04 | définition des TdR | §2, FR-05 | A |
| R05 | gabarits variables | FR-24 | B |
| R06 | critique du cahier | v0.2 | ce lot |
| R07, R23 | fenêtre et limites | FR-26 | B |
| R08 | pages, images, graphiques | FR-27 | E |
| R09, R10, R24 | modèle interchangeable | FR-28 | C |
| R11, R25 | données et raisonnement métier | §8, FR-19 | D |
| R12, R29 | tableau de bord client | FR-31 | F |
| R13 | rôle du faux modèle | NFR-05 | reporté |
| R20 | client utilisateur | FR-30 | G |
| R21 | espace diagnostics, priorité de lecture | FR-22 | A |
| R22 | contexte par chat | FR-23, FR-25 | B |
| R26 | dossier d'entraînement | FR-29, NFR-07 | D |
| R27 | studio | FR-29 | C |
| R28 | début de l'entraînement | après validation des données | D |
| R30 | domaine financier | §9 | reporté |
| R31 | apprentissage | docs 03 | continu |

## 11. Lots

| Lot | Contenu | Dépend de | Fini quand |
|---|---|---|---|
| A Cœur métier | rôles, priorités, projets, chaîne, contrôles | correctif de contexte | les 9 contrôles testés, parcours réel lu |
| B Contexte et rédaction | fiche, chat, gabarits, jauge | A pour le lien à l'initiative | trois types de projet générés et relus |
| C Modèles et studio | registre, changement, studio local, paquet Colab | export prouvé | changement et retour arrière testés, palier court mesuré |
| D Données | pipeline, validation, entraînement | validation humaine | jeu validé, rapport complet |
| E Documents | OCR, tableaux, vision optionnelle | — | couverture affichée sur scans réels |
| F Tableau de bord client | proposition, audit, construction | champs de A | aucun chiffre sans champ source |
| G Client | rôle, parcours, isolation | A, B | parcours client et approbation consultant testés |

| Mois | Priorité |
|---|---|
| 1 | A, jeu de validation, remesure après correctif |
| 2 | B, revue par un consultant |
| 3 | C, D |
| 4 | E, F |
| 5 | G, évaluation humaine de H7 |
| 6 | pilote, sécurité, soutenance |

## 12. Sources métier

Seules la FAQ Colab et la page d'import d'Ollama ont été lues en entier. Les autres ont été consultées par **extraits de recherche** : elles orientent la conception et ne valent pas conformité. Les méthodes internes d'EY et des autres cabinets ne sont pas publiques.

- Deloitte, [partir de l'état actuel, de la vision et des écarts](https://www.deloitte.com/dk/en/services/consulting/perspectives/configuring-the-transformation-roadmap-using-the-capability-model.html)
- EY, [Transformation Delivery](https://www.ey.com/en_us/services/consulting/transformation-delivery-solution) : partir de la cible, livrer par paliers visibles
- RSM, [contenu d'une feuille de route](https://www.rsm.global/australia/insights/building-cohesive-business-transformation-roadmap)
- Banque mondiale, [sélection de consultants, section Termes de référence](https://thedocs.worldbank.org/en/doc/797021501871857713-0290022017/render/RFPSelectionofConsultantsFRENCHFINAL.pdf)
- Marchés publics, [plan d'un CCTP](https://www.marche-public.fr/Plans/Plan_CCTP.htm)
- OMS, [suivi des recommandations d'audit](https://www.who.int/about/office-of-internal-oversight-services/dashboards/internal-audit) ; ACCA, [suivi des actions](https://www.accaglobal.com/sg/en/member/sectors/internal-audit/learn/management-actions.html) : distinguer « déclaré fait » de « vérifié »
- Ollama, [import](https://docs.ollama.com/import) et [fenêtre de contexte](https://docs.ollama.com/context-length)
