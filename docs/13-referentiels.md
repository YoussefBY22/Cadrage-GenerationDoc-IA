# 13 — Référentiels : ce qui s'applique, ce que fait le projet, ce qui manque

Lot REF. En conseil et en IT, on travaille selon des normes. Ce document les identifie, dit **pourquoi** elles
s'appliquent à Cadrage, **ce que le projet fait déjà**, l'**écart** et l'**action**. Principes : sources
officielles uniquement (liens en §5), **aucun texte protégé recopié** (les normes ISO et le guide ITIL sont payants :
on cite leur titre et leur idée, jamais leur contenu), et **la preuve d'abord** — un référentiel cadre la structure
d'un livrable, il ne remplace **jamais** une source du client (invariant : voir `prompting.py`, ligne « RÉFÉRENTIELS »).

> Les références de clauses ne sont données que lorsque la source officielle les expose publiquement. Les points
> juridiques (AI Act, RGPD) sont une **analyse de projet étudiant**, à faire valider par un juriste avant tout usage client.

## 1. Référentiels qui cadrent les livrables (utilisés par l'IA)

| Référentiel | Pourquoi ici | Ce que le projet fait déjà | Écart | Action |
|---|---|---|---|---|
| **ISO/IEC/IEEE 29148:2018** (ingénierie des exigences) | Le cahier des charges est un document d'exigences : énoncés identifiés, non ambigus, vérifiables, avec méthode de vérification | Gabarit `cdc` en 5 sections (périmètre, fonctionnelles, non fonctionnelles, contraintes, recette) | Pas d'identifiants ni de critères d'acceptation exigés | **Fait (REF)** : `cdc` demande REQ-n / NFR-n, un énoncé vérifiable par phrase, critères d'acceptation et méthode (inspection, analyse, démonstration, essai) en recette |
| **Banque mondiale** : *Writing Terms of Reference for an Evaluation* + exemples de ToR (PPP) | Les ToR de bailleurs suivent une trame : contexte, objectifs, livrables, calendrier, profil, évaluation pondérée | Gabarit `tor` en 6 sections inspiré de ces trames (lot EN) | Références non explicites | **Fait** : chaque section de `tor` cite la rubrique correspondante |
| **UE : PM²** (guide de gestion de projet de la Commission) et **gestion du cycle de projet** (INTPA) | Initiation, dossier d'affaires, livrables, critères d'acceptation ; logique d'intervention des projets UE | Idem | Le guide GCP/INTPA n'a pas pu être retrouvé par la recherche : à relire à la source | **Fait** pour PM² ; à confirmer pour la GCP |
| **OCDE-CAD** : critères d'évaluation (pertinence, cohérence, efficacité, efficience, impact, durabilité) | Section « critères d'évaluation » d'un ToR | Section `evaluation` du `tor` | Critères libres | **Fait** : section `evaluation` référencée aux critères CAD ; la liste exacte vient des sources du client |
| **ISO 31000:2018** (risques) | Section « Risques » de la feuille de route : identifier, analyser (vraisemblance × conséquence), évaluer, traiter | Section `risques` sourcée ; scoring multicritère des initiatives | Pas de structure vraisemblance / conséquence / traitement | **Fait** : consigne `risques` (vraisemblance et conséquence si les passages les donnent ; traitement éviter, réduire, transférer, accepter **si sourcé**) |
| **ISO 21502** / PMBOK / PRINCE2 (projet) | Phasage, jalons, dépendances d'une feuille de route | Vagues, dépendances, chemin critique (`roadmap/graph.py`) | Pas de lien explicite | **Fait** : sections `synthese`, `calendrier` référencées (ISO 21502 / PM²). PMBOK et PRINCE2 : pas de référence directe (licences payantes, 21502 et PM² suffisent) |
| **COBIT 2019** (ISACA) | 40 objectifs de gouvernance et de gestion en 5 domaines (EDM, APO, BAI, DSS, MEA) : langage courant des diagnostics IT | Thème libre par constat | Aucun étiquetage | **Fait** : champ `domain` d'une initiative (COBIT ou ITIL), validé contre la liste officielle des 40 objectifs (`roadmap/referentiels.py`), **proposé seulement si un passage le justifie** |
| **ITIL 4** (PeopleCert/AXELOS) | 34 pratiques de gestion (14 générales, 17 de services, 3 techniques) | Idem | Idem | **Fait** : même champ, validé contre les 34 pratiques |
| **TOGAF** (The Open Group) | Architecture d'entreprise : alignement stratégie ↔ architecture | Aucun | Hors périmètre d'un MVP | Référencé comme cadre de lecture de la section `axes` ; pas d'étiquetage (recherche non concluante, à vérifier) |

## 2. Référentiels du produit lui-même (IA responsable et sécurité)

| Référentiel | Pourquoi ici | Ce que le projet fait déjà | Écart | Action |
|---|---|---|---|---|
| **Règlement (UE) 2024/1689 « AI Act »** | Le produit est un système d'IA générative déployé en UE | Voir classification §3 et matrice §4 | Documentation d'usage, mention de transparence | Rédiger une notice d'usage et une mention « généré par IA, relu par un humain » sur les exports |
| **ISO/IEC 42001:2023** (système de management de l'IA) | Norme certifiable de gouvernance de l'IA, structure ISO (clauses 4-10, PDCA) ; ce que EY ou un client demandera | Journal d'audit, versions, états de validation, évaluation chiffrée | Pas de politique IA, de registre de risques, de revue de direction | Rédiger une politique IA d'une page et un registre de risques (§4) ; viser l'alignement, pas la certification |
| **ISO/IEC 23894:2023** (risques de l'IA) | Guide pour appliquer le management du risque à l'IA | Risques connus dans `05-revue-perimetre.md` et le rapport | Pas de registre structuré par processus ISO 31000 | Registre de risques IA (hallucination, injection, fuite, biais, dérive) lié aux tests |
| **NIST AI RMF 1.0** (NIST AI 100-1) + profil IA générative (AI 600-1) | Cadre volontaire GOVERN / MAP / MEASURE / MANAGE, référence mondiale | Banc d'évaluation (MEASURE), refus sans preuve (MANAGE) | GOVERN et MAP peu écrits | Voir matrice §4 |
| **ISO/IEC 27001:2022** | Sécurité de l'information : contrôles d'accès, journalisation, sauvegarde | Auth par jetons, mots de passe hachés, réseau interne, sauvegardes (`10-exploitation.md` §6) | Pas de SMSI ni d'analyse de risques formelle | Utiliser la liste de contrôle comme base de déclaration d'applicabilité |
| **RGPD** (règlement (UE) 2016/679) | Les diagnostics peuvent contenir des données personnelles | 100 % local, journal sans contenu, pas d'envoi externe | Pas de registre des traitements ni de durée de conservation | Registre art. 30, durée de conservation, AIPD si usage réel (art. 35) |
| **OWASP Top 10 for LLM Applications** | Liste de référence des risques des applications LLM | Défense contre l'injection (`security/`), sorties validées par schéma | Vérifier le millésime en vigueur (une édition 2025 existe ; une plus récente peut exister) | Matrice §4 |

## 3. Classification du cas d'usage (AI Act) — analyse du projet

- **Rôle** : le projet est un **système d'IA** construit sur des modèles d'IA à usage général tiers (Qwen, BGE-M3).
  Les obligations des **fournisseurs de modèles** (documentation technique, droit d'auteur, résumé des données
  d'entraînement) pèsent sur ceux-ci ; Cadrage est en aval.
- **Haut risque (annexe III)** : l'annexe III vise huit domaines précis (emploi, éducation, services essentiels,
  application de la loi…). Un assistant qui **rédige des documents de cadrage de projet à partir de diagnostics
  d'organisation** ne prend aucune décision sur des personnes : il n'entre pas dans ces cas. Il **cesserait** d'être
  « hors annexe III » s'il servait par exemple à évaluer des candidats ou des agents (le gabarit ToR « profil »
  décrit un poste, il n'évalue personne). **Conclusion** : risque limité, **à confirmer par un juriste**.
- **Transparence (art. 50)** : un système qui génère du texte doit en marquer les sorties de façon lisible par machine
  (50.2) ; le texte publié pour informer le public sur des sujets d'intérêt public doit être signalé comme généré par
  IA sauf relecture humaine avec responsabilité éditoriale (50.4). Le circuit de validation humaine du projet
  (états `draft` → validé, export bloqué sinon) va dans ce sens ; il **manque** un marquage dans les exports.
- **Calendrier** : les dates d'application échelonnées et les modifications récentes figurent dans le texte consolidé
  d'EUR-Lex : à relire avant toute mise en production.
- **RGPD art. 22** : pas de décision individuelle automatisée ; l'IA propose, l'humain valide.

## 4. Matrice de conformité du produit

Statut : **Oui** = en place et testé ; **Partiel** = en place, incomplet ; **Non** = à faire. Les renvois sont des
fichiers existants du dépôt.

| Exigence (référentiel) | Statut | Où le projet y répond |
|---|---|---|
| **AI Act** — supervision humaine (art. 14, principe) | Oui | Circuit `draft → validé`, export bloqué sinon : `app/workflow/`, `06-architecture.md` §8 |
| **AI Act** — transparence sur les sorties (art. 50) | Partiel | Citations vérifiées dans chaque phrase (`app/verification/`) ; **marquage « généré par IA » des exports : Non** |
| **AI Act** — tenue de registres / traçabilité | Oui | Journal d'audit et `record_run` (prompt haché, modèle, latence) : `app/services/generation.py` |
| **AI Act** — exactitude et robustesse | Partiel | Vérificateur de nombres et de citations ; refus sans preuve (porte de pertinence, lot Q2) ; `backend/eval` |
| **AI Act** — littératie IA des utilisateurs (art. 4) | Partiel | Glossaire et notes d'usage (`03-apprentissage-et-glossaire.md`) ; formation utilisateur : Non |
| **ISO 42001** — politique et rôles (cl. 5) | Non | À rédiger (politique IA d'une page) |
| **ISO 42001** — évaluation des risques IA (cl. 6, 8) | Partiel | Risques dans `05-revue-perimetre.md` ; registre structuré : Non |
| **ISO 42001** — évaluation des performances (cl. 9) | Oui | Banc `backend/eval`, résultats Q / Q2 dans `docs/STATUS.md` |
| **ISO 42001** — amélioration continue (cl. 10) | Partiel | Lots itératifs avec mesures avant/après (`docs/lots/`) |
| **NIST AI RMF** — GOVERN | Partiel | Rôles et états de validation ; politique : Non |
| **NIST AI RMF** — MAP (contexte, usages prévus) | Partiel | `01-cahier-des-charges.md`, `05-revue-perimetre.md`, §3 ci-dessus |
| **NIST AI RMF** — MEASURE | Oui | `backend/eval` (refus, taux de phrases appuyées), tests de sécurité |
| **NIST AI RMF** — MANAGE | Partiel | Refus sans preuve, relecture humaine ; plan de réponse aux incidents : Non |
| **OWASP LLM01** — injection de prompt | Oui | Passages balisés par nonce, neutralisés : `app/security/sanitize.py`, `injection.py` ; `tests/security/` |
| **OWASP LLM02** — divulgation d'informations sensibles | Partiel | Modèle local, journal sans contenu ; contrôle d'accès par dossier : `app/auth/` |
| **OWASP LLM05** — traitement incorrect des sorties | Oui | Sorties JSON validées par schéma Pydantic (`llm_schemas.py`), jamais exécutées |
| **OWASP LLM06** — agence excessive | Oui | Aucun outil ni action déclenchée par le modèle |
| **OWASP LLM09** — désinformation | Oui | Citation obligatoire, vérificateur, refus `insufficient_evidence` |
| **OWASP LLM10** — consommation non bornée | Partiel | Budget de passages et de jetons (`prompting.py`) ; quotas par utilisateur : Non |
| **RGPD** — minimisation, localité (art. 5, 25) | Oui | Réseau Docker interne, aucun appel sortant (`tests/test_no_outbound.py`) |
| **RGPD** — sécurité (art. 32) | Partiel | Mots de passe hachés, jetons, sauvegardes (`10-exploitation.md`) ; chiffrement au repos : Non |
| **RGPD** — registre, conservation, AIPD (art. 30, 35) | Non | À rédiger si usage avec données réelles |

## 5. Ce que EY publie lui-même (public)

D'après les pages publiques d'EY consacrées à l'IA responsable : un cadre à **neuf principes** (responsabilité,
protection des données, fiabilité, transparence, explicabilité, équité, conformité, durabilité, sécurité), ancré
dans une gouvernance et une assurance indépendante ; une version antérieure, le cadre « Trusted AI », parlait de
cinq caractéristiques (transparente, explicable, non biaisée, résiliente, performante). Les pages régionales
diffèrent ; **à citer comme positionnement d'EY, non comme norme**.

Correspondance avec le projet : responsabilité → validation humaine et audit ; protection des données → local ;
fiabilité → vérificateur et banc d'évaluation ; transparence et explicabilité → citation de chaque phrase ;
sécurité → défense contre l'injection. Équité et durabilité : non traitées (le produit ne décide rien sur des
personnes ; la sobriété d'un modèle de 4 milliards de paramètres local reste à documenter).

## 6. Sources officielles

- ISO/IEC/IEEE 29148:2018 : <https://www.iso.org/standard/72089.html> (une révision est à l'étude)
- ISO 31000 : <https://www.iso.org/standards/popular/iso-31000-family> ; ISO/IEC 27001 : <https://www.iso.org/publication/PUB200270.html>
- ISO/IEC 42001 : <https://www.iso.org/home/insights-news/resources/iso-42001-explained-what-it-is.html> ; ISO/IEC 23894 : <https://www.iso.org/standard/77304.html>
- NIST AI RMF 1.0 : <https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf> ; profil IA générative : <https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf>
- AI Act : <https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng> ; FAQ art. 50 : <https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act>
- RGPD et IA : <https://www.cnil.fr/fr/intelligence-artificielle/ia-comment-etre-en-conformite-avec-le-rgpd>
- Banque mondiale, *Writing ToR for an Evaluation* : <https://documents1.worldbank.org/curated/en/209341599772583527/pdf/Writing-Terms-of-Reference-for-an-Evaluation-A-How-to-Guide.pdf> ; ToR types : <https://ppp.worldbank.org/sample-tors-project>
- PM² : <https://pm2.europa.eu/pm2-methodologies/pm2-project-management_en>
- COBIT 2019 (ISACA) : <https://www.isaca.org/resources/news-and-trends/industry-news/2019/employing-cobit-2019-for-enterprise-governance-strategy> ; ITIL 4 : <https://www.axelos.com/resource-hub/practice/readers-manual-itil-4-practice-guide>
- OWASP LLM Top 10 : <https://genai.owasp.org> (vérifier l'édition en vigueur)
- EY, IA responsable : <https://www.ey.com/en_us/insights/ai/principles-for-ethical-and-responsible-ai>

**Limites de la recherche** : OCDE-CAD, TOGAF, ISO 21502, GCP/INTPA, PMBOK et PRINCE2 n'ont pas été confirmés par une
page officielle dans cette passe ; leurs références dans les gabarits sont des **noms**, sans clause. Les numéros de
clauses ISO ne sont pas cités faute de source publique gratuite.
