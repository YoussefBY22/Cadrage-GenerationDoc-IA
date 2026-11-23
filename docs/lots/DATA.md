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

## Mise à jour 23/11 (soir) : rapports spéciaux de la Cour 2023-2026, cinq tâches

Cause du premier échec sur Colab : les réponses d'entraînement écrivaient `missing_evidence` avant `sentences`, alors que la grammaire d'Ollama impose
l'ordre du schéma (`status`, `sentences`, `missing_evidence`). Chaque réponse est maintenant sérialisée dans l'ordre du schéma (`training/dataset/schema_order.py`, test et contrôle du paquet).

Source principale : 103 rapports spéciaux de la Cour des comptes européenne en français (2023 : 19, 2024 : 28, 2025 : 26, 2026 : 30), CC BY 4.0 (mentions légales de la Cour), avec les réponses de la Commission quand elles existent
(décision 2011/833/UE, CC BY 4.0). Adresses et SHA-256 de chaque PDF : `MANIFEST.json` du paquet (`rapports_cour`). Seuls les PDF publics sont lus ; User-Agent générique, pause entre les requêtes.
**Limite** : 2018 à 2022 non couverts. Seul le schéma d'adresse 2023-2026 (`ECAPublications/SR-AAAA-NN/…_FR.pdf`) est prévisible ; avant, le nom de fichier contient un titre. L'API interne du site n'a pas été utilisée.

Tâches (`meta.task_type`, invites de l'application ; `position` et `conflit` : nouvel appel `app/services/stance.py`, schéma `LLMStance`) :
- `extraction` : paragraphes du rapport (+ recommandation et échéance) -> constats, phrases recopiées ; **thème et gravité écrits par des règles de mots-clés de l'assistant** ;
- `position` : recommandation + réponse de la Commission -> accept / partial / reject ; l'étiquette est la position officielle (« accepte / accepte partiellement / n'accepte pas ») ; variante difficile : toutes les réponses de la recommandation dans le passage ;
- `conflit` : recommandation + justification d'une acceptation partielle ou d'un rejet (conflict), ou d'une acceptation (aligned) ; ce sont des positions réelles de la Commission, pas une stratégie de client : à lire comme « contrainte exprimée par l'institution » ;
- `feuille_de_route` : recommandations + « Quand ? » réels -> initiatives (ordre du rapport) ou calendrier (ordre des échéances) ; aucune date inventée ;
- `refus` : preuve retirée (pas d'échéance ; pas de réponse de la Commission ; pas de contrainte) -> `insufficient_evidence` ; **le texte de `missing_evidence` est écrit par l'assistant** (phrase type).

Séparation par rapport (un rapport et ses réponses = un groupe, jamais des deux côtés ; aucun passage identique entre entraînement et test/validation).
Effectifs : 535 exemples ; entraînement 341, validation 25, test 169.
- train par tâche : {'autre': 13, 'conflit': 35, 'extraction': 73, 'feuille_de_route': 47, 'position': 92, 'redaction_cdc': 1, 'redaction_tdr': 4, 'refus': 76} ; par lot : {'eca-2023-2026': 319, 'pilote-v2': 17, 'pilote-v3': 5}
- val par tâche : {'autre': 3, 'conflit': 1, 'divergence': 3, 'extraction': 4, 'feuille_de_route': 4, 'position': 4, 'redaction_cdc': 3, 'refus': 3} ; par lot : {'eca-2023-2026': 11, 'pilote-v2': 4, 'pilote-v3': 10}
- test par tâche : {'autre': 4, 'conflit': 24, 'divergence': 2, 'extraction': 31, 'feuille_de_route': 25, 'position': 50, 'redaction_cdc': 1, 'redaction_tdr': 1, 'refus': 31} ; par lot : {'eca-2023-2026': 152, 'pilote-v2': 7, 'pilote-v3': 10}
- étiquettes de position, entraînement : {'accept': 74, 'aligned': 18, 'conflict': 17, 'partial': 14, 'reject': 4} ; test : {'accept': 28, 'aligned': 8, 'conflict': 16, 'partial': 17, 'reject': 5}

Limites : les acceptations dominent (la Commission accepte la plupart des recommandations) ; les rejets sont rares (peu pour apprendre, peu pour mesurer). Le « conflit » n'oppose pas une recommandation à la stratégie d'un client ;
il faudra des exemples de ce type (stratégie « 50 recrutements par an » contre « recruter davantage ») que ces sources ne fournissent pas. Aucun exemple n'a été relu par un humain.
