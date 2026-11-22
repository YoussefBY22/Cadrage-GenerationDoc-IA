# Apprendre en construisant — glossaire et plan

Ce document a deux usages : **comprendre le vocabulaire** du projet, et **apprendre en parallèle** de son avancement. L'agent cloud le complète au fil des phases.

---

## 1. Glossaire (en français simple)

**LLM (grand modèle de langage)** : un programme qui a appris, sur d'énormes quantités de texte, à **prédire la suite** d'un texte. Il ne « sait » pas, il **continue** de façon plausible.

**Jeton (token)** : un morceau de mot (« cahier », « des », « charges »). Le modèle lit et écrit des jetons, pas des phrases. Les coûts et les limites se mesurent en jetons.

**Prédiction du prochain jeton** : à chaque pas, le modèle calcule une **probabilité pour chaque jeton possible**, en choisit un, l'ajoute, et recommence. Un texte entier se fabrique jeton après jeton.

**Température** : réglage du **hasard** dans ce choix. Basse (proche de 0) : le modèle prend presque toujours le jeton le plus probable → réponses stables, prévisibles (bon pour extraire ou vérifier). Haute : plus de variété, plus de risque d'erreurs (bon pour brainstormer). Dans notre projet : **basse** pour les citations et les chiffres.

**Top-p / top-k** : autres façons de limiter le choix aux jetons les plus probables.

**Fenêtre de contexte** : la quantité de texte que le modèle peut « avoir sous les yeux » en une fois. Au-delà, il oublie ou on doit découper.

**Prompt** : le texte qu'on donne au modèle (consignes + données). Un **prompt système** fixe son rôle et ses règles.

**Hallucination** : le modèle affirme avec assurance quelque chose de faux. C'est normal pour un modèle qui « continue un texte plausible ». D'où nos **vérificateurs**.

**Ancrage (grounding)** : obliger le modèle à répondre **à partir de passages fournis**, et à les citer.

**Embedding** : une liste de nombres qui représente le **sens** d'un texte. Deux textes proches par le sens ont des embeddings proches.

**Base vectorielle (pgvector)** : une base capable de trouver les textes dont l'embedding est le plus proche de celui d'une question.

**RAG (génération augmentée par recherche)** : *examen à livre ouvert*. Avant de répondre, le système **cherche** dans les documents du client les passages utiles, les **colle dans le prompt**, et le modèle répond **en s'appuyant dessus** en citant ses sources. Le modèle n'apprend rien de façon permanente : les documents restent dans la base.

**Découpage (chunking)** : couper les documents en passages (par exemple de quelques paragraphes) pour pouvoir les retrouver et les citer.

**Recherche mixte (hybride)** : combiner la recherche **par sens** (embeddings) et **par mots-clés** (BM25). Chacune rattrape les oublis de l'autre.

**Reclassement (reranking)** : un second modèle réordonne les passages trouvés pour mettre les plus pertinents en premier.

**Fine-tuning (adaptation)** : continuer l'entraînement d'un modèle sur **des exemples** pour changer **sa façon de répondre** (format, ton, habitudes). Ça n'apprend pas des faits fiables : pour les faits, on utilise le RAG.

**LoRA / QLoRA** : on n'entraîne que de **petites couches ajoutées** au modèle au lieu de tout le modèle (beaucoup moins de mémoire). **QLoRA** : même chose sur un modèle **compressé**.

**Quantification** : compresser un modèle (moins de bits par nombre) pour qu'il tienne en mémoire. Légère perte de qualité, gros gain de place.

**Inférence / entraînement** : utiliser le modèle (inférence) ≠ le modifier (entraînement). L'entraînement coûte bien plus cher.

**Modèle « open-weight » (à poids ouverts)** : modèle dont on peut télécharger les poids et l'exécuter chez soi, selon une **licence** (à lire).

**Injection de consigne (prompt injection)** : un document contient « ignore tes règles… » pour manipuler le modèle. On traite les documents comme **non fiables**.

**Évaluation** : mesurer la qualité avec des chiffres (citations valides, chiffres exacts, structure respectée) et des relectures humaines, sur un **jeu d'essai** séparé de l'entraînement.

**Ablation** : comparer plusieurs configurations en retirant ou ajoutant une pièce (modèle seul / + RAG / + adaptation) pour voir **ce qui apporte vraiment**.

**On-premise** : installé **chez le client**, sur son serveur.

**Entrepôt de données (data warehouse)** : base organisée pour **analyser** (pas pour saisir). **Modèle en étoile** : des **faits** (événements mesurables) entourés de **dimensions** (qui, quoi, quand).

**ETL** : extraire, transformer, charger : copier les données de l'application vers l'entrepôt.

---

## 2. Quatre idées à retenir avant de commencer

1. Un LLM **ne cherche pas la vérité**, il **prolonge un texte**. Sans documents, il invente.
2. **RAG = donner les bons documents au bon moment.** Fine-tuning = **changer ses habitudes**.
3. La **qualité** du système vient surtout de la **recherche**, du **vérificateur** et de l'**évaluation**, pas de la taille du modèle.
4. En conseil, **le consultant est responsable** : l'outil prépare, l'humain valide.

---

## 3. Plan d'apprentissage en parallèle (8 semaines)

Chaque semaine : **≈ 3 h** de cours + relire le « Pour comprendre » de la phase en cours.

| Sem. | Phase du projet | À apprendre | Pour vérifier que tu as compris |
|---|---|---|---|
| 1 | A. Squelette | Rappels LLM : jeton, prédiction, température, contexte, hallucination. Cours *AI Capabilities and Limitations* à reprendre. | Explique à un ami pourquoi un LLM invente. |
| 2 | B. Ingestion | Embeddings, similarité, bases vectorielles, découpage, recherche mixte. | Décris ce qui se passe quand je pose une question au RAG. |
| 3 | B. Recherche | Évaluer une recherche (rappel, précision), reclassement. | Pourquoi une recherche par mots-clés peut battre les embeddings ? |
| 4 | C. Génération | Sorties structurées (JSON), citations, refus sans preuve, injection de consignes. | Que vérifie notre vérificateur, et que ne vérifie-t-il pas ? |
| 5 | D. Interface | Cycle de relecture, versions, exports de documents. | Quels états de validation, et pourquoi bloquer l'export ? |
| 6 | E. Entrepôt | Modèle en étoile, ETL, bases de Power BI (modèle de données, mesures simples). | Dessine l'étoile de notre projet. |
| 7 | F. Adaptation | Fine-tuning, LoRA/QLoRA, quantification, surapprentissage, jeux d'entraînement/validation/essai. | Quand préférer RAG à l'adaptation ? |
| 8 | F/G. Évaluation | Ablation, métriques, évaluation humaine, rédiger un résultat honnête. | Comment prouver que l'adaptation apporte quelque chose (ou non) ? |

## 4. Ressources (à chercher par leur nom)

Je n'ai pas vérifié les liens : cherche les titres.

- **Bases IA / ML** : *Machine Learning Crash Course* (Google, gratuit) ; *Introduction to Generative AI* (Google Cloud Skills Boost) ; vidéos *Intro to Large Language Models* et *Let's build GPT* d'Andrej Karpathy ; série *Neural Networks* de 3Blue1Brown (chapitres sur les transformeurs).
- **Pratique des LLM** : *Hugging Face LLM Course* (gratuit) ; documentation d'**Ollama** ; documentation de **LlamaIndex** ou **LangChain** (pour comprendre les pièces d'un RAG, même si on les code nous-mêmes).
- **Fine-tuning** : guides *Unsloth* et la bibliothèque *PEFT* de Hugging Face ; lire une fois un article sur QLoRA.
- **Power BI** : parcours *Microsoft Power BI Data Analyst* (PL-300) sur Microsoft Learn (gratuit) ; la certification est un bon bonus pour ton CV.
- **Anthropic** : reprends les cours de l'académie Anthropic ; la certification que tu as déjà t'a donné les bases.
- **Anglais technique** : lis les fiches de modèles sur Hugging Face : tu y trouveras licences, tailles et limites.

## 5. Les compétences à maîtriser, par ordre d'urgence

1. **Vocabulaire LLM** (ce glossaire) : sans lui, tu ne comprendras pas les décisions du projet.
2. **RAG** : le cœur du produit.
3. **Évaluer** un système d'IA avec des chiffres.
4. **Python** de base (lire du code, lancer des scripts) : l'essentiel de l'IA est en Python.
5. **SQL et modèle en étoile** : pour l'entrepôt et Power BI.
6. **Fine-tuning** : à comprendre en gros, tu n'as pas besoin de coder les calculs.
7. **Sécurité et confidentialité** : ce qui peut fuir, et comment on l'évite.

---

## 6. Notions ajoutées en cours de projet

**Interface (`LLMProvider`)** *(phase A)* : une « prise standard ». Le reste du code branche n'importe quel modèle dessus, comme un appareil sur une prise normalisée. Changer de modèle ne casse rien.

**Faux modèle / déterminisme** *(phase A)* : un programme qui imite un modèle mais renvoie **toujours la même réponse pour la même entrée**. Sans GPU, il permet de vérifier que toute la chaîne fonctionne ; les vrais modèles, eux, varient.

**Graine aléatoire (seed)** *(phase A)* : le « point de départ » du hasard. Même graine + même température basse = résultats reproductibles, donc chiffres refaisables (contrainte C4).

**Sortie structurée / schéma JSON** *(phase A, utilisée en C)* : on donne au modèle un **formulaire** à remplir (champs, types) au lieu de le laisser écrire librement ; le code peut alors **valider** la réponse automatiquement.

**Test de contrat** *(phase A)* : on vérifie qu'un composant envoie bien les bonnes requêtes à un **serveur simulé**, sans le vrai service. C'est ainsi qu'on teste Ollama sans modèle.

**Réseau Docker « internal »** *(phase A)* : un réseau privé entre conteneurs, **sans porte vers Internet**. La base de données y est enfermée.

**Journal sans contenu** *(phase A)* : on note « un texte de 412 caractères, empreinte ab12… » et jamais le texte lui-même, pour qu'aucune donnée client ne fuite dans les journaux.

**BM25** *(phase B)* : la formule classique de recherche **par mots-clés**. Un mot rare présent dans un passage compte beaucoup ; un mot très courant compte peu ; un passage très long est un peu pénalisé. Imbattable pour les noms propres et les chiffres.

**RRF (Reciprocal Rank Fusion, fusion par rangs réciproques)** *(phase B)* : pour combiner deux classements (mots-clés et sens), on donne à chaque passage `1 / (60 + son rang)` dans chaque classement et on additionne. Comme un jury de deux juges qui classent les candidats : on ne compare pas leurs notes, seulement les **places**. Simple et robuste.

**Rappel@k, MRR** *(phase B)* : le **rappel@10** est la part des questions pour lesquelles le bon passage figure dans les 10 premiers résultats. Le **MRR** regarde à quelle **place** il arrive (1ʳᵉ place = 1, 2ᵉ = 0,5…).

**Reranking (reclassement)** *(phase B, optionnel)* : un modèle plus lent relit la question **et** chaque passage ensemble pour réordonner les 30 premiers. Plus précis, plus coûteux : prévu pour le serveur, pas pour le PC à 4 Go.

**Couche de stockage abstraite (dépôt / repository)** *(phase B)* : le code demande « donne-moi les passages du dossier X » sans savoir si la base est SQLite (tests) ou PostgreSQL (production). Comme une prise électrique standard, encore.

**Étiquettes de passages (P1, P2…)** *(phase C)* : le modèle ne voit pas les longs identifiants, seulement `P1…P10` ; le code refait la correspondance. Moins de recopie, moins d'erreurs.

**Nonce** *(phase C)* : un code aléatoire, différent à chaque appel, placé dans les balises qui entourent les passages. Un document piégé ne peut pas « fermer » la balise car il ne connaît pas ce code.

**Mode « preuve d'abord »** *(phase C)* : on extrait d'abord des **constats** sourcés, l'humain les valide, puis on rédige la feuille de route et les termes de référence **à partir des constats validés**.

**TPV (taux de phrases vérifiées)** *(phase C)* : part des phrases dont toutes les sources existent et dont tous les chiffres se retrouvent dans les sources. L'indicateur central du projet. Il prouve l'**ancrage**, pas la vérité.

**Normalisation des nombres** *(phase C)* : ramener « 1 250 », « 1,25 millier » et « 1250 » à la même valeur avant de comparer.

**Canari** *(phase C)* : un mot unique (`ZX-CANARI-7`) caché dans un document piégé. S'il ressort dans la réponse, l'attaque a réussi : c'est mesurable.

**Quatre yeux** *(phase D)* : la personne qui approuve un livrable ne peut pas être celle qui l'a écrit. Principe de contrôle interne classique en audit.

**Grain d'un fait** *(phase E)* : ce que représente **une ligne** d'une table de faits (« une tentative de génération d'une section », « une transition de validation »). On le fixe **avant** de choisir les colonnes ; mélanger deux grains dans une table fausse les sommes.

**Dimension / fait / clé de substitution** *(phase E)* : un **fait** mesure (latence, nombre de phrases) ; une **dimension** décrit (quel modèle, quel client, quel jour). La clé de substitution est un simple numéro interne qui relie les deux.

**ETL incrémental et idempotent, filigrane (watermark)** *(phase E)* : on ne recopie que ce qui est nouveau depuis la dernière date chargée (le filigrane) ; relancer deux fois ne crée pas de doublons.

**Mesure DAX** *(phase E)* : formule de Power BI calculée selon les filtres de la page (par exemple le TPV d'un seul client).

**Distance d'édition (edit ratio)** *(phase E)* : combien le consultant a réécrit le texte proposé, de 0 (rien changé) à 1 (tout réécrit).

**Intervalle de confiance par bootstrap** *(phase F)* : on retire des centaines de fois, au hasard et avec remise, l'échantillon de sections pour voir comment varie le résultat. Si l'intervalle du gain C − B reste au-dessus de 0, le gain n'est probablement pas dû au hasard.

**Q4_K_M, GGUF** *(phase F)* : format de fichier de modèle (GGUF) et niveau de compression courant (environ 4 bits par poids) utilisés par Ollama et llama.cpp.

**Fuite de données d'évaluation** *(phase F)* : si un même document sert à l'entraînement et au test, le score est trop beau. D'où le découpage **par document source**.

### Notions des phases B à G (consolidées au lot R2)

**Contrat / modèle gelé** *(B0)* : signature ou modèle de données qu'aucun lot ne change sans le signaler ; les modèles Pydantic sont « gelés » (non modifiables après création), comme un formulaire signé. **Routeur découvert** : fichier `routes_*.py` inclus automatiquement par l'application, sans toucher à `main.py`.

**Migration Alembic, clé étrangère** *(B1)* : une migration est une étape versionnée qui fait évoluer le schéma de la base (avec retour arrière). Une clé étrangère interdit de pointer vers une ligne qui n'existe pas.

**pgvector, HNSW, similarité cosinus, force brute** *(B1)* : pgvector ajoute les vecteurs à PostgreSQL ; HNSW est un index qui trouve les voisins approximativement, très vite ; la similarité cosinus mesure l'angle entre deux vecteurs ; la force brute compare avec tous (exacte, lente sur de gros volumes, suffisante en test).

**Signature de fichier (magic bytes)** *(B2)* : les premiers octets qui révèlent le vrai format ; on la vérifie en plus de l'extension, qu'un fichier piégé peut falsifier.

**Section_path** *(B2)* : chemin des titres d'un passage (« 2 > 2.1 Gouvernance ») qui sert de repère de citation.

**Injection indirecte, texte caché, faux positif** *(B2)* : consigne cachée dans un document du client (police minuscule, caractères de largeur nulle). Le détecteur la **signale** sans supprimer le passage. Un faux positif est une alerte sur un texte normal.

**Mots vides, racinisation, IDF, chevauchement** *(B3)* : mots vides = mots ignorés (« le », « de ») ; racinisation = ramener « financements » à « financ » ; IDF = poids d'un mot d'autant plus fort qu'il est rare ; chevauchement = quelques mots répétés entre deux passages voisins pour ne pas couper une idée.

**Corpus « or », phrase-marqueur, document piégé** *(B4)* : jeu de documents fabriqués à partir de faits connus ; chaque fait porte une phrase unique qui prouve qu'un passage est le bon ; les documents piégés contiennent des attaques ou des chiffres contradictoires.

**Empreinte SHA-256, ingestion** *(B5)* : l'empreinte identifie un fichier (deux contenus identiques, même empreinte), d'où le refus de doublons. L'ingestion est la chaîne taille → lecture → découpage → alertes → vecteurs → stockage.

**Gabarit, budget de contexte, instantané (snapshot)** *(C1)* : le gabarit liste les sections d'un livrable ; le budget limite le nombre de passages donnés au modèle ; un test d'instantané compare un prompt à une version de référence.

**Appui lexical, écho d'instruction** *(C2)* : l'appui lexical mesure le recouvrement de mots pleins entre une phrase et sa source (un indice, pas une preuve) ; l'écho d'instruction détecte une consigne piégée reprise dans la réponse. Le vérificateur prouve l'ancrage, pas la véracité.

**Refus (« preuves insuffisantes »), run de génération** *(C4)* : sans assez de passages le système refuse **avant** d'appeler le modèle. Un run enregistre une tentative de génération (modèle, durée, résultat).

**Tri topologique, chemin critique, cycle** *(C3)* : le tri topologique range les initiatives pour que chaque prérequis passe avant (algorithme de Kahn) ; le chemin critique est la file de tâches la plus longue, qui fixe la durée totale ; un cycle (A attend B qui attend A) est détecté et signalé. Le score de priorité est la somme pondérée des critères ramenés sur 0–1 (coût et risque inversés).

**Acquittement, jeton opaque** *(D1)* : le relecteur accepte explicitement une phrase en échec ou un refus (consigné). Un jeton opaque est une chaîne aléatoire sans contenu lisible ; seule son empreinte est stockée.

**Annexe Sources, conversion headless, Gantt** *(D2)* : liste numérotée des passages cités ; conversion en PDF par LibreOffice sans interface ; planning en barres (vagues, durées).

**App Router, jeton porteur (Bearer), XSS, vitest** *(D3a)* : routage Next.js par dossiers ; en-tête `Authorization: Bearer …` ; XSS = injection de script par du texte affiché comme HTML (d'où aucun `dangerouslySetInnerHTML`) ; vitest = lanceur de tests du front.

**TipTap / ProseMirror, nœud, NodeView, diff** *(D3b)* : bibliothèque d'éditeur ; chaque phrase est un nœud portant son statut (vert, orange, rouge) et ses sources ; un diff montre ce qui a changé entre deux versions.

**Pseudonymisation, vue SQL** *(E1)* : remplacer les noms réels par des identifiants stables dans l'entrepôt ; une vue est une requête enregistrée, lue par Power BI comme une table.

**Données de démonstration, BOM UTF-8, Metabase** *(E2)* : fausses données marquées `is_demo` ; le BOM est un marqueur d'encodage que lit Excel ; Metabase est un tableau de bord libre, alternative à Power BI.

**Appariement, simulation** *(F1)* : comparer deux configurations sur les **mêmes** sections (intervalle plus étroit) ; la simulation est un faux modèle qui se trompe à taux fixe pour valider la grille de mesure.

**Point de reprise (checkpoint), early stopping, distillation** *(F2)* : sauvegarde intermédiaire d'un entraînement ; arrêt quand la qualité ne progresse plus ; distillation = faire écrire les exemples par un modèle plus fort (« professeur » local).

**Proxy inverse, paquet hors ligne (bundle)** *(G1)* : le proxy (nginx) reçoit les requêtes et les relaie aux services internes sans jamais appeler dehors ; le bundle est un dossier autonome (images, dépendances, empreintes) installable sans Internet.

**Référentiel, norme, cadre** *(REF)* : un document public qui dit « comment bien faire » (ISO 29148 pour écrire des exigences, COBIT pour gouverner l'IT, NIST AI RMF pour gérer les risques de l'IA). Il **cadre la structure** d'un livrable ; il n'est jamais une preuve : les faits viennent des sources du client.

**Exigence vérifiable (REQ-n)** *(REF, ISO/IEC/IEEE 29148)* : un énoncé « le système doit… », unique, sans ambiguïté, qu'on peut contrôler (inspection, analyse, démonstration ou essai) ; on la numérote pour la retrouver en recette. Analogie : une règle de jeu qu'un arbitre peut trancher.

**COBIT 2019 / ITIL 4 / TOGAF** *(REF)* : COBIT = 40 objectifs de gouvernance IT en 5 domaines (EDM, APO, BAI, DSS, MEA) ; ITIL 4 = 34 pratiques de gestion des services ; TOGAF = méthode d'architecture d'entreprise. Une initiative peut porter l'étiquette d'un domaine COBIT ou d'une pratique ITIL, seulement si un passage le justifie.

**ISO 31000 / ISO/IEC 23894** *(REF)* : méthode de gestion du risque (identifier, analyser vraisemblance et conséquence, évaluer, traiter) ; 23894 l'applique à l'IA.

**AI Act, ISO/IEC 42001, NIST AI RMF** *(REF)* : règlement européen sur l'IA (classe les usages par niveau de risque), norme certifiable de management de l'IA, cadre volontaire américain (GOVERN, MAP, MEASURE, MANAGE). La matrice de `13-referentiels.md` y relie le code.

**OWASP Top 10 for LLM** *(REF)* : liste des dix risques majeurs des applications à base de modèles de langage (injection de prompt, fuite d'information, sortie non contrôlée…).
