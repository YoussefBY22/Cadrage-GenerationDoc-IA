# Lot DATA : sources publiques du jeu d'entraînement (pilote v3)

Recherche faite le 23/11/2026 avec des requêtes génériques (sans nom de personne ni de projet) et un User-Agent générique.
« Publié en ligne » ne vaut pas licence : une source n'est retenue que si une page l'énonce (preuve ci-dessous).

## Sources retenues (3 rapports de la Cour, 2 réponses de la Commission, 4 pièces de marché : 9 documents)

| Source | Éditeur | Licence et preuve | Documents exploitables | Paire entrée → sortie |
|---|---|---|---|---|
| Rapports spéciaux 26, 27, 28/2024 (FR) <https://www.eca.europa.eu/ECAPublications/SR-2024-28/SR-2024-28_FR.pdf> | Cour des comptes européenne | **CC BY 4.0**. Mention dans le PDF (page de droits : « fait l'objet d'une licence CC BY 4.0 ») et <https://www.eca.europa.eu/fr/legal-notice> (décision n° 6-2019). Réserve : « sauf indication contraire », ne pas altérer le sens, indiquer les modifications | 7 rapports téléchargés et contrôlés (24-26, 24-27, 24-28, 25-24, 26-04, 26-13, 26-14, tous avec la mention CC BY 4.0), 3 utilisés ; la Cour en publie bien davantage, non comptés | constats (« Nous avons constaté… ») → recommandation + échéance « Quand? D'ici à fin 2025 » : **feuille de route reliée à un audit** ; constats numérotés → extraction de constats |
| Réponses de la Commission aux rapports 27/2024 et 13/2026 <https://www.eca.europa.eu/Lists/ECAReplies/COM-Replies-SR-2024-27/COM-Replies-SR-2024-27_FR.pdf> | Commission européenne, hébergé par la Cour | Le PDF ne porte **aucune mention** ; couvert par la mention du site de la Cour et par la décision 2011/833/UE (CC BY 4.0) : à confirmer par l'orchestrateur | 6 téléchargées (rapports 24-26, 24-27, 24-28, 25-24, 26-04, 26-13), 2 utilisées | recommandation de la Cour ↔ réponse (« accepte partiellement… ») : divergence entre deux sources |
| CCTP « services numériques en mode produit » (2025, annexe sécurité 2025, CCTP 2021) <https://www.data.gouv.fr/datasets/accord-cadre-interministeriel-realisation-de-services-publics-numeriques-en-mode-produit-agile-pilote-par-limpact> | DINUM (beta.gouv.fr) | **Licence Ouverte 2.0** : champ `license = lov2` de la fiche data.gouv.fr (API publique `/api/1/datasets/<slug>/`) | 3 CCTP (+ 3 CCAP, non retenus : clauses juridiques) | passages d'un CCTP → autre section du même CCTP : cahier des charges, et unités d'œuvre à valeur de TdR |
| Cahier des charges « portage de repas » (2025) <https://www.data.gouv.fr/datasets/marche-de-service-livraison-en-liaison-froide-de-repas-a-domicile-de-personnes-dependantes-avec-veille-sociale> | CCAS de Rochefort | **Licence Ouverte 2.0** (`lov2`, même preuve) | 1 cahier des charges (+ 1 règlement de consultation) | articles → section (périmètre, contraintes, exigences) |

## Sources exclues, et pourquoi

- **Banque mondiale (TdR, documents de projet)** : le dépôt (OKR) publie « sous CC BY 3.0 IGO, CC BY-NC, CC BY-SA ou autres termes » **œuvre par œuvre** (<https://www.banquemondiale.org/ext/fr/legal/terms-conditions/open-knowledge-repository>, lue) ; l'API des documents répond 403 à un client automatique, je ne l'ai pas contournée. Aucun TdR à licence confirmée : **exclu tant qu'un document précis n'est pas vérifié**. Piste : choisir des documents CC BY 3.0 IGO un par un.
- **PNUD (centre d'évaluation, TdR, réponses de la direction)** : la page des conditions d'utilisation répond 403 ; licence non établie. Exclu.
- **OIF (TdR)** : page de mentions légales introuvable (404). Les TdR exigent des livrables en CC BY-SA mais ne disent rien de leur propre licence. Exclu.
- **AFD, ONG (Médecins du Monde, Solthis, Coordination SUD…)** : TdR trouvés par la recherche, aucune licence de réutilisation vue. Exclus.
- **Cour des comptes française** : les jeux de données associés sont en ODbL, mais la licence des rapports eux-mêmes n'a pu être lue (ccomptes.fr inaccessible depuis mon client). Exclu. **vie-publique.fr** : d'après le résultat de recherche, les métadonnées sont en Licence Ouverte mais les PDF « droits non gérés » (page non lue en entier) ; exclu.
- **data.gouv.fr, jeux sans licence** (`notspecified`) : DCE de la DINUM/SGMAP, marché de mentorat, communes, hôpitaux. Exclus.
- **Commission, analyses d'impact (pilote v2)** : déjà utilisées (CC BY 4.0), non reprises pour ne pas surreprésenter une source.

## Décisions et limites

1. **Aucune paire « diagnostic → TdR / CdC » humaine à licence vérifiée n'a été trouvée.** Les types TdR et CdC sont donc des exemples de **format** : un passage d'un CCTP ou cahier des charges réel, une section de gabarit, des phrases recopiées du même document. Les « TdR » sont des unités d'œuvre de CCTP (livrables, profils, délais), pas de vrais TdR. À dire à l'utilisateur.
2. La feuille de route est la paire la plus proche du besoin : audit (constats) → recommandations avec échéances, écrit par la Cour.
3. Les « contradictions » sont des **divergences de position** (la Commission « accepte partiellement ») et non des contradictions factuelles.
4. **Écrit par l'assistant** : la consigne des exemples « divergence » ; le thème et la gravité des constats ; l'assemblage « amorce + alinéa » en une phrase (18 phrases sur 74). Tout le reste est du texte humain recopié (vérifié mot pour mot à la construction).
5. Séparation **par document** : test = rapport 26/2024, réponses 13/2026, CCTP 2021, annexe sécurité 2025 ; aucun document des deux côtés (test automatique).
6. Reste à faire avant tout entraînement : relecture humaine de la page `validation-25-exemples.html`, confirmation de la licence des réponses de la Commission.
7. Le texte des PDF et le jeu restent dans `training/data/` (ignoré par Git) ; le dépôt ne garde que le code (`training/dataset/v3_*.py`) et les phrases de sortie, extraits courts sous licence (attribution : Cour des comptes européenne, DINUM, CCAS de Rochefort).

## Reproduire

```
python -m training.dataset.v3_sources --sources-dir DOSSIER --fetch
python -m training.dataset.v3_build --sources-dir DOSSIER --out-dir training/data/pilote-v3
```
`render_prompt` n'existe pas dans `train_lora.py` : l'invite est rendue par `app.generation.prompting` (`build_section_prompt`, `build_findings_prompt`), la fonction de l'application ; un test le vérifie.

## Paquet d'entraînement Colab (23/11, branche `feature/entrainement-4b`)

`training/colab/cadrage-donnees-publiques.zip` (dans le dépôt : documents publics seulement, SHA-256 vérifié par le carnet) :
28 exemples v2 relus (les 2 exemples « Profil » et « Calendrier » des TdR sont écartés : l'application ne les envoie plus au modèle) + 25 v3.
Effectifs : entraînement 33 (8 documents), validation 7 (2 documents), test 13 (6 documents), aucun document des deux côtés.
Les invites v2 sont refaites avec `app.generation.prompting` et les gabarits actuels ; les v3 sont reconstruites sur la version actuelle de `main`.
Les 2 exemples v3 qui pointaient sur des sections de décision (profil, calendrier) ont été remplacés par des sections « contexte » et « objectifs ».
Rien n'a été relu par un humain : décision de l'utilisateur, à garder en tête pour toute conclusion.
Les invites d'entraînement n'ont pas de fiche de contexte (« CONTEXTE … ») ni de décisions D1..Dn : l'application peut en ajouter à l'inférence.
