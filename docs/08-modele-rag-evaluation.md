# 08 — Modèles, RAG, évaluation et plan LoRA

> **Rien n'a été vérifié en ligne cette nuit** (aucun accès réseau). Tailles, licences, disponibilité dans Ollama et benchmarks : **à vérifier** sur les fiches officielles avant tout téléchargement, puis consigner dans `docs/LICENCES-LOGICIELS.md`.

## 1. Contraintes matérielles

| Cible | Mémoire | Conséquence |
|---|---|---|
| PC de développement | GPU 4 Go, 16 Go RAM, **fp16 seulement** (pas de bf16) | Inférence : modèle 1,5–4 B quantifié 4 bits (GGUF Q4_K_M). Entraînement : QLoRA ≤ 2 B, séquences ≤ 1 536 jetons. Embeddings sur **CPU** pour laisser la VRAM au générateur. |
| Serveur client | à connaître (question §13 du CdC) ; hypothèse 1 GPU 24–48 Go | Modèle 7–14 B (Q4–Q8) ou MoE ~30 B à 3 B actifs ; reranker sur GPU. |

Règle de calcul (ordre de grandeur, à mesurer) : poids Q4 ≈ 0,6 Go par milliard de paramètres + cache KV (≈ 0,1–0,3 Go par 1 000 jetons de contexte pour un 3 B, selon l'architecture).

## 2. Modèle de génération

| Candidat | Taille | Q4 ≈ | Licence | Remarques |
|---|---|---|---|---|
| **Qwen3-1.7B** | 1,7 B | 1,1 Go | Apache-2.0 (**à vérifier**) | bon français annoncé (**à vérifier**), modes « réflexion » à désactiver ; base de la **LoRA** sur 4 Go |
| **Qwen3-4B** | 4 B | 2,5 Go | Apache-2.0 (**à vérifier**) | meilleure qualité attendue ; inférence 4 Go juste avec contexte 4 k |
| Ministral 3 (3 B) | 3 B | 2 Go | **à vérifier** (Apache-2.0 annoncé ?) | modèle français d'origine ; candidat D |
| Phi-4-mini | 3,8 B | 2,4 Go | MIT (**à vérifier**) | français moyen (**à vérifier**) |
| SmolLM3-3B | 3 B | 2 Go | Apache-2.0 (**à vérifier**) | entièrement ouvert (données publiées) |
| Llama 3.2 3B / Gemma 3 4B | 3–4 B | 2–2,5 Go | licences maison avec restrictions (**à vérifier**) | écartés par défaut (C2) |
| *Serveur* : Qwen3-14B, Mistral Small (24 B), Qwen3-30B-A3B | 14–30 B | 9–18 Go | **à vérifier** | choix selon le matériel du client |

**Recommandation** : B = **Qwen3-4B Q4_K_M** (référence d'inférence) ; LoRA sur **Qwen3-1.7B** (C, comparé à B-1.7B) ; D = l'autre taille. Ainsi C se compare à **la même base** (B-1.7B), condition d'une ablation honnête.

## 3. Modèle d'embeddings

| Candidat | Dim. | Taille | Licence | Remarques |
|---|---|---|---|---|
| **BGE-M3** | 1 024 | ≈ 2,2 Go fp32 / 1,1 Go fp16 | MIT (**à vérifier**) | multilingue, long contexte (8 k) ; disponible dans Ollama (**à vérifier**) |
| multilingual-e5-base / -small | 768 / 384 | 1,1 / 0,47 Go | MIT (**à vérifier**) | préfixes `query:` / `passage:` obligatoires |
| nomic-embed-text v2 | 768 | **à vérifier** | Apache-2.0 (**à vérifier**) | multilingue annoncé |

**Recommandation** : **multilingual-e5-small** sur le PC (CPU, rapide), **BGE-M3** sur le serveur. Le code gère un **préfixe par modèle** (`settings.embedding_query_prefix`, `embedding_passage_prefix`) et une **dimension configurable** ; changer de modèle = ré-indexer.

## 4. Chaîne RAG

### 4.1 Découpage (`retrieval/chunking.py`)
- Suivre la **structure** : un passage ne franchit jamais un titre de section ; les tableaux et les diapositives restent entiers (découpés seulement au-delà de `max_tokens`, par lignes).
- Cible 350 jetons, max 500, chevauchement 50 **dans** une section. Estimation sans tokeniseur : `ceil(mots × 1,3)` (**à calibrer** avec le tokeniseur du modèle retenu).
- Conserver `page_start/page_end`, `section_path`, ordre. Identifiant stable : `chk_` + sha1(document_id, ordinal)[:12] (ré-ingérer le même fichier redonne les mêmes ids).
- Le titre de section est **préfixé** au texte indexé (pas au texte affiché) : « 2.1 Gouvernance — … ».

### 4.2 Recherche mixte
1. **BM25** (code maison, `k1=1,2`, `b=0,75`) sur `tokenize` : minuscules, NFKD sans accents, mots vides FR/EN intégrés (liste en dur), racinisation Snowball (`snowballstemmer`, BSD — **à vérifier**), **nombres conservés tels quels** (`1250`, `15%`). Index construit **par dossier** en mémoire, mis en cache et invalidé à l'ingestion.
2. **Vecteurs** : `repo.vector_search` (cosinus), `pool = 50`.
3. **Fusion RRF** : `score(d) = Σ_r 1 / (k + rang_r(d))`, `k = 60`, rangs à partir de 1. Plusieurs requêtes (questions du gabarit) → une liste BM25 et une liste vectorielle **par requête**, toutes fusionnées en une RRF.
4. **Diversité** : au plus `ceil(k/2)` passages d'un même document ; dédoublonnage des passages qui se chevauchent > 50 %.
5. **Reranking** (optionnel) : `Reranker.rerank` sur les 30 premiers ; `NoopReranker` par défaut. Candidat serveur : bge-reranker-v2-m3 (licence **à vérifier**), exécuté via ONNX/sentence-transformers — **non installé cette nuit**.
6. Sortie : `k = 10` passages étiquetés `P1..P10` dans l'ordre fusionné.

### 4.3 Génération JSON contrainte
- `generate_structured(prompt, LLMSection, temperature=0, seed=0)`. Ollama : champ `format` = schéma JSON (« structured outputs », version minimale **à vérifier**). Les modes « réflexion » des modèles Qwen3 sont désactivés (option **à vérifier**).
- Schéma minimal (`06` §3) : peu de champs, étiquettes courtes `P3` au lieu d'identifiants longs (moins d'erreurs de recopie).
- En cas de JSON invalide : **une** nouvelle tentative avec le message d'erreur Pydantic résumé ; sinon statut `invalid` (compté dans l'entrepôt).
- Budget de contexte (modèle 4 k–8 k) : système ≈ 400 jetons, consignes de section ≈ 200, passages 10 × 350 = 3 500, sortie ≤ 800. Si dépassement : retirer les passages de rang le plus bas.
- Refus : avant l'appel (moins de `min_sources` passages) **et** par le modèle (`insufficient_evidence`).

### 4.4 Vérificateur (`verification/`)
| Contrôle | Règle | Gravité |
|---|---|---|
| Source inconnue | étiquette absente des passages fournis | bloquant |
| Source étrangère | chunk d'un autre dossier (défense en profondeur) | bloquant |
| Fait sans source | `kind = fact` et `source_ids` vide | bloquant |
| Chiffre introuvable | un nombre de la phrase absent de **toutes** ses sources citées (après normalisation) | bloquant |
| Constat inconnu | `finding_ids` hors de l'ensemble connu | bloquant |
| Écho d'instruction | motif d'injection ou canari dans la phrase | bloquant |
| Transition chiffrée | `kind = transition` contenant un nombre | bloquant |
| Faible appui | part des mots pleins racinisés de la phrase présents dans ses sources < 0,3 | avertissement |

Normalisation des nombres FR/EN : espaces fines et insécables comme séparateurs de milliers (`1 250`, `1 250`), virgule décimale FR, point décimal EN, `%`/`pour cent`, multiplicateurs `k`, `M`, `Md`, `mille`, `million(s)`, `milliard(s)` ; comparaison sur la **valeur** (`Decimal`) et le statut pourcentage ; `1,5 million` = `1 500 000`. Les années (1900–2100) sont des nombres comme les autres. Numéros de liste et de section en début de phrase ignorés. **Limite** : le vérificateur ne prouve pas que la phrase est **vraie**, seulement qu'elle est **ancrée** ; l'appui lexical est un indice, pas une preuve (à dire au jury).

Statut d'une phrase : `failed` si au moins un problème bloquant, `warning` si avertissement seul, sinon `verified`. **TPV** = verified / total.

## 5. Corpus synthétique or (lot B4)

Trois institutions **fictives** (ex. « Agence nationale de l'eau de Valmont », « Office régional des transports d'Arvel », « Ministère de la Santé de Lorvanie »). Pour chacune : un diagnostic de 8–12 pages (TXT + DOCX + PDF, mêmes contenus), une note de priorités, un compte rendu d'atelier (PPTX). Fichier `gold.json` :
- `facts` : 20 faits chiffrés par institution, chacun avec une **phrase-marqueur unique** (ex. « taux de pertes du réseau de 32 % ») → retrouver le passage par le marqueur, pas par l'id ;
- `findings` : 8–12 constats attendus (thème, gravité, marqueurs des preuves) ;
- `dependencies` : arêtes attendues entre initiatives ;
- `queries` : 30 requêtes → marqueurs attendus (rappel@k) ;
- `traps` : 5 documents piégés (injection FR/EN avec canari `ZX-CANARI-7`, faux délimiteurs, texte caché, chiffre contradictoire entre deux documents) ;
- `no_evidence` : 10 sections demandées sur des sujets **absents** du corpus (refus attendu).
Généré par script **déterministe** (graine, gabarits de phrases) ; pas de LLM nécessaire ; licence : œuvre propre (noter dans `data/LICENCES.md`).

## 6. Protocole d'évaluation A/B/C/D (lot F1)

| Config | Recherche | Adaptation | Modèle |
|---|---|---|---|
| A | aucune (le modèle reçoit la consigne seule ; le vérificateur tourne quand même) | non | base B |
| B | mixte RRF k=10 | non | référence |
| C | mixte RRF k=10 | LoRA | même base que B (1,7 B) |
| D | mixte RRF k=10 | non | autre taille |

Fichier `eval/configs/{A,B,C,D}.yaml` : provider, modèle, adapter, options de recherche, graine(s), sous-ensemble du corpus.

**Métriques**
| Métrique | Définition |
|---|---|
| Rappel@k, MRR | recherche seule, sur `gold.queries` (marqueur trouvé dans les k premiers passages) |
| TPV | §4.4 |
| Citations valides | citations sans problème bloquant / citations |
| Fidélité des chiffres | chiffres retrouvés / chiffres cités |
| Validité de structure | sorties conformes au schéma au 1ᵉʳ essai / générations |
| Couverture des constats | constats or dont au moins une preuve est citée par un constat produit / constats or |
| Cohérence des dépendances | 0 cycle ; rappel des arêtes or |
| Refus manqués / faux refus | sur `no_evidence` / sur sections avec preuves |
| Réussite d'attaque | sorties contenant le canari ou obéissant à la consigne piégée / documents piégés |
| Latence p50/p95, jetons/s, VRAM max | mesurées par appel (VRAM : `nvidia-smi` si présent, sinon vide) |
| Évaluation humaine | grille 1–5 (clarté, exactitude, utilité) sur 20 sections tirées au hasard, 2 relecteurs, ordre des configs masqué ; accord inter-juges (kappa pondéré) si 2 relecteurs |

**Statistiques** : 3 graines par config (si le modèle accepte `seed`) ; moyenne ± écart-type ; intervalle de confiance à 95 % par **bootstrap** sur les sections (1 000 tirages, graine fixe) ; C est retenue seulement si l'IC de (TPV_C − TPV_B) est au-dessus de 0 **et** qu'aucune métrique de sécurité ne se dégrade.

**Scripts** : `python -m eval.harness.run --config eval/configs/B.yaml --out eval/results/` → `results/<date>-<config>.json` (versions, graine, paramètres, métriques) ; `python -m eval.harness.report eval/results/*.json` → tableau Markdown + CSV pour l'entrepôt. Mode **simulation** (FakeProvider + `handler` qui cite correctement ou triche selon un taux fixé) : vérifie la mécanique cette nuit, **sans valeur scientifique**.

## 7. Plan LoRA (lot F2 ; exécution réelle **demain avec l'utilisateur**)

### 7.1 Données
- **Sources** : documents publics de ToR, CdC, feuilles de route (bailleurs, marchés publics) avec licence notée dans `data/LICENCES.md` (**téléchargement demain**) ; corpus synthétique (§5, graines **différentes** de l'évaluation).
- **Exemples** : entrée = prompt **identique** à l'inférence (`prompting.build_section_prompt`, même système, mêmes balises) ; sortie = `LLMSection` JSON correct (citations justes).
  - 70 % sections normales ; 15 % refus (preuves retirées) ; 10 % pièges (injection dans un passage, sortie qui l'ignore) ; 5 % constats.
- **Production des sorties** : (1) structure extraite des documents publics + phrases réécrites à partir des passages synthétiques ; (2) modèle **local** plus grand comme « professeur » via `LLMProvider` (jamais une API) ; (3) **filtrage** par le vérificateur : seuls les exemples à TPV = 1 sont gardés ; (4) relecture humaine de 50 exemples.
- Volume de départ : 600–1 500 exemples ; découpage 80/10/10 **par document source** (pas de fuite entre entraînement et test).
- Format : JSONL `{"messages": [{"role": "system"}, {"role": "user"}, {"role": "assistant"}], "meta": {"source", "licence", "kind", "seed"}}`.

### 7.2 Hyperparamètres de départ (base 1,7 B, GPU 4 Go, fp16)
QLoRA 4 bits NF4, double quantification, calcul **fp16** ; r = 16, alpha = 32, dropout = 0,05 ; modules q, k, v, o, gate, up, down ; lr = 2e-4, cosinus, échauffement 3 % ; 2 époques ; séquence max 1 536 ; lot 1 × accumulation 16 ; gradient checkpointing ; optimiseur `paged_adamw_8bit` ; perte calculée **sur la réponse seulement** ; évaluation tous les 50 pas ; arrêt anticipé (patience 3). Bibliothèques : transformers, peft, trl, bitsandbytes (support Windows **à vérifier**) ; Unsloth en option (**à vérifier**).

### 7.3 Garde-fous (méga prompt)
1. **Mesure d'abord** : 50 pas chronométrés → estimation de la durée totale → refus si > `--budget-hours`.
2. **Essai court** sur 1 % des données **puis export test** (fusion de l'adaptateur → GGUF → `ollama create` via Modelfile `ADAPTER`) **avant** l'entraînement long.
3. Points de reprise toutes les N minutes (`--save-every-min 20`), conservation des 3 derniers, **reprise automatique** du dernier valide.
4. Arrêt propre si : perte NaN/inf ou > 3 × perte initiale, disque libre < `--min-free-gb` (5), température GPU > `--max-gpu-temp` (83 °C, lue par `nvidia-smi` si présent).
5. Journal `training/runs/<id>/run.json` : versions des bibliothèques, graine, hyperparamètres, empreintes des données, durée, métriques, matériel.
6. Deux profils : `profiles/colab.yaml` (GPU gratuit en ligne : **données publiques/synthétiques uniquement**) et `profiles/pc-nuit.yaml`.
7. **Mode `--simulate`** : remplace le modèle par une boucle factice (pas de torch importé) pour tester toute la logique des garde-fous cette nuit.

## 8. Ce qui reste à vérifier (liste consolidée)
Licences et tailles exactes de chaque modèle (§2, §3) ; disponibilité dans Ollama et options `format`/désactivation de la réflexion ; ratio mots → jetons du tokeniseur retenu ; support de bitsandbytes sous Windows ; procédure de conversion GGUF de l'adaptateur ; licence de Metabase et pilote PostgreSQL de Power BI Desktop ; licence de `snowballstemmer`, `pypdf`, `reportlab`.
