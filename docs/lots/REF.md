# Lot REF — référentiels

## Fait
- Recherche web (sources officielles, liens dans `docs/13-referentiels.md` §6) ; tableau référentiel → pourquoi → existant → écart → action ; classification AI Act ; matrice de conformité du produit (AI Act, 42001, NIST AI RMF, OWASP LLM, RGPD) renvoyant au code.
- Gabarits `{fr,en}` : champ `referentiels` au niveau du gabarit et de **chaque section** (`template_loader.py`) ; le CdC suit ISO/IEC/IEEE 29148 (REQ-n / NFR-n vérifiables, critères d'acceptation, méthode de vérification), les ToR citent Banque mondiale, PM², OCDE-CAD, la section risques s'appuie sur ISO 31000.
- Prompt de section : ligne « RÉFÉRENTIELS » (références courtes, déclarées cadre de structure, **jamais une source**), placée après les passages.
- Feuille de route : champ facultatif `domain` (domaine COBIT 2019 ou pratique ITIL 4) proposé par le modèle si un passage le justifie ; `app/roadmap/referentiels.py` le valide contre les 40 objectifs et les 34 pratiques, sinon `None`.

## Testé
`tests/generation/test_referentiels.py`, `tests/roadmap/test_referentiels.py` (FakeProvider, sans Ollama) : chargement, références par section, alignement fr/en, présence dans les prompts, normalisation des domaines. Instantané de prompt mis à jour. Suite : 2 échecs, dont `test_ci_has_frontend_and_training_jobs` (CI, antérieur au lot, hors périmètre).

## Limites
Pas de mesure avec le vrai modèle (GPU occupé) : l'effet des consignes REQ-n sur qwen3:4b reste à évaluer. OCDE-CAD, TOGAF, ISO 21502, GCP/INTPA non confirmés par page officielle. Analyse juridique à faire valider.

## Écarts aux contrats de 06
`Initiative.domain` (facultatif, par défaut `None`, rétrocompatible) dans `app/domain/roadmap.py` ; une ligne dans `services/roadmap_service.py` pour le renseigner. Fichiers hors périmètre, changements minimaux.

## Demandes
Marquage « généré par IA » sur les exports (hors périmètre). Éventuel test de `docs/13` par un juriste.

## Pour comprendre
Un référentiel est un modèle de plan, pas une source de faits : comme un sommaire type de rapport, il dit quelles rubriques prévoir et comment les formuler, mais le contenu vient du client.

## 3 questions
1. Pourquoi une référence de norme ne doit-elle jamais apparaître dans « sources » ? 2. Pourquoi valider l'étiquette COBIT contre une liste ? 3. Qu'est-ce qui rendrait ce produit « haut risque » au sens de l'AI Act ?

## Notions pour le glossaire
Référentiel, exigence vérifiable (REQ-n), COBIT/ITIL/TOGAF, ISO 31000/23894, AI Act/42001/NIST AI RMF, OWASP LLM (ajoutées à `03`).
