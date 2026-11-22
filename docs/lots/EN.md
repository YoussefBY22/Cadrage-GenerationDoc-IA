# Lot EN — livrables en français et en anglais

Le français reste la référence ; l'anglais s'ajoute par paramétrage, sans dupliquer la logique.

- **Gabarits** : `backend/app/generation/templates/en/{findings,roadmap,tor,cdc}.yaml`, mêmes clés,
  limites et `uses_findings` que le français (test d'alignement). Structures génériques inspirées des
  trames publiques des bailleurs (contexte et justification, objectifs, livrables, calendrier, profils,
  critères d'évaluation ; périmètre, exigences, contraintes, recette), sans marque.
- **Prompts** : `system_prompt(lang)` et libellés par langue dans `prompting.py` ; mêmes garde-fous
  (données balisées par nonce, refus `insufficient_evidence`, JSON seul). Le prompt anglais demande de
  rédiger en anglais même si les passages sont dans une autre langue.
- **Langue par livrable** : champ optionnel `language` (`fr|en`) sur `POST /dossiers/{id}/deliverables`
  et `POST /dossiers/{id}/roadmap:generate` ; défaut = langue du dossier (compatible). La génération de
  sections suit la langue du livrable, pas celle du dossier ; les constats suivent la langue du dossier.
- **Vérificateur** : nombres anglais (`1,250.5`, `3.2 bn`, `3.2 billion`, `4 thousand`, `15 percent`,
  `15 per cent`, `mn`). Dossier mixte : les nombres des sources sont lus selon les deux conventions ;
  `billion` n'est pas mis à l'échelle en français (faux ami).
- **Exports** : libellés DOCX/PPTX et pied de page selon `content.language` (`export/common.py::LABELS`).
  Pas de document de référence DOCX anglais : le style par défaut est utilisé.
- **Tests** : `tests/generation/test_en_parcours.py` (FakeProvider et modèle demo, dossier anglais et
  mixte, exports), nombres anglais et dossier mixte dans `tests/verification`, alignement des gabarits.
- Fichiers hors périmètre touchés (changements minimes, `lang=`) : `services/findings.py`,
  `services/roadmap_service.py`.
