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
