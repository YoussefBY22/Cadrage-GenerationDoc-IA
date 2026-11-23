# Lot B — Contexte et rédaction (décisions, fiche, chat, gabarits par type de projet)

## Fait
- **Décisions humaines (FR-23)** : table `decisions` (catégorie, texte, auteur, date, statut proposée / confirmée), API `/dossiers/{id}/decisions`, `/decisions/{id}` (`:confirm`, `:retract`), écran « Décisions ». Seules les confirmées comptent ; modifier le texte retire la confirmation.
- **Génération** : les décisions confirmées arrivent au modèle étiquetées `D1..Dn`, neutralisées, comptées dans la fenêtre (40 % au plus, les catégories exigées d'abord). Le vérificateur les accepte comme une source (`decision_ids`), les chiffres sont comparés à leur texte ; l'export les affiche « Décision de <auteur>, <date> ».
- **Sections de décision** : chaque section déclare `requires_decisions`. Sans décision confirmée de la bonne catégorie : refus **sans appel au modèle** (« décision humaine requise : profil »). Avec elles, la section est **rendue sans modèle**, une phrase par décision confirmée de la catégorie, telle quelle et citée (`decision_ids`) : mesuré sur qwen3:4b, le modèle recopiait le diagnostic ou attribuait le texte d'une décision à un passage. Les autres sections reçoivent les décisions (D1..Dn, 40 % de la fenêtre, non-envoi signalé).
- **Faux ancrage** : une phrase qui cite un passage mais dont un nombre (même en lettres) ou le texte vient d'une décision absente du passage est bloquée (`FOREIGN_SOURCE`, non acquittable).
- **Création et confirmation** : une décision se crée toujours « proposée » (422 sinon) ; `:confirm` est un second appel audité (`decision.create`, `decision.confirm`). L'interface enchaîne les deux au clic « Enregistrer et confirmer ».
- **Fiche de contexte (FR-25)** : table `context_sheets`, `GET/PUT /dossiers/{id}/context` (brouillon, puis confirmation ; toute modification retire la confirmation). Seule la fiche confirmée entre dans les prompts (cadre, jamais une source) et choisit les modules par défaut.
- **Chat** : `POST /dossiers/{id}/chat`. Il lit fiche, décisions et passages balisés, répond court et **propose** champs et décisions ; il n'écrit rien. Historique non stocké et jamais citable. Propositions écartées avec raison : champ ou catégorie invalide, consigne cachée, chiffre absent du message, des passages ou de l'historique, doublon. Fenêtre pleine : refus explicite sans appel ; l'historique ancien est rogné et signalé.
- **Gabarits (FR-24)** : tronc commun + 8 modules (`templates/modules/*.yaml`, FR et EN) : logiciel et SI, données et IA, infrastructure et travaux, fournitures, services et externalisation, étude et conseil, organisation et conduite du changement, formation. Combinables, ordre canonique, sections ajoutées et sections du tronc adaptées (jamais retirées) ; `referentiels` conservés ; chaque module déclare ses décisions exigées. `GET /templates/{tor|cdc}`, `GET /templates/modules`. Le livrable garde ses `modules` ; verrou d'approbation inchangé (il exige les sections du gabarit exact).
- Migration `0004` (montée et descente testées). Faux modèle `demo` : sections de décision et chat.

## Testé
`tests/services/test_decisions.py` (13), `tests/api/test_decisions_api.py` (4, migration), `tests/api/test_context_chat.py` (14), `tests/generation/test_modules.py` (24), vitest `decisions`, `context`, `modules`. Cas réel : `test_profil_avec_seulement_des_constats_est_refuse_sans_appel`.

## Limites
- Aucun essai sur le vrai modèle : le comportement de qwen3:4b face aux sections de décision et au chat reste à mesurer.
- La confirmation d'une décision n'exige pas un relecteur (un membre du dossier suffit) ; à trancher.
- Le sélecteur de modules n'est pas dans l'interface : les modules viennent de la fiche confirmée (ou de l'API).
- Le chat est sans mémoire côté serveur ; sa qualité dépend du modèle.

## Écarts aux contrats de 06
- `dim_issue` de l'entrepôt est figé à 10 codes : pas de nouveau code d'anomalie, `UNKNOWN_SOURCE` et `FACT_WITHOUT_SOURCE` portent un détail propre aux décisions.
- `test_engine_migrations` : 19 → 21 tables ; le test de parcours confirme d'abord les décisions du TdR.

## Demandes
Valider les catégories de décision et les modules ; mesurer le chat sur le vrai modèle.

## Pour comprendre
Un TdR est un bon de commande : le diagnostic dit ce qui ne va pas, pas combien on paie ni qui on engage. Ces choix sont posés par une personne, datés et signés, puis cités comme des pièces. Sans pièce, le secrétaire (le modèle) n'écrit rien : il n'a même pas été appelé.

## 3 questions
1. Pourquoi refuser avant l'appel plutôt que filtrer après ?
2. Pourquoi le chat ne peut-il rien écrire, même s'il se trompe ?
3. Pourquoi un module adapte le tronc sans jamais en retirer une section ?

## Notions pour le glossaire
Décision humaine · section de décision · fiche de contexte · module de gabarit.
