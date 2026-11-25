# training/ — jeu d'entraînement et scripts LoRA sûrs (lot F2)

Tout est testé **sans GPU ni torch** (mode `--simulate`). L'entraînement réel est prévu avec l'utilisateur (T5).

## 1. Préparer le jeu (aucun LLM, aucun réseau)
Depuis la racine du dépôt, avec le venv du backend :
```powershell
backend\.venv\Scripts\python -m training.dataset.build  --n-seeds 20      # candidats (graines 1000+, ≠ évaluation)
backend\.venv\Scripts\python -m training.dataset.filter                    # garde les exemples à TPV = 1
backend\.venv\Scripts\python -m training.dataset.split                     # 80/10/10 par document source
```
Format : JSONL `{"messages":[system,user,assistant], "meta":{source,licence,kind,seed}}`. Le prompt vient de
`app.generation.prompting` (identique à l'inférence). Répartition : 70 % sections, 15 % refus, 10 % pièges
(injection ignorée), 5 % constats. Un exemple sans `meta.licence` est refusé. Pour des données publiques
réelles (T4), ajouter leurs exemples avec la licence notée dans `data/LICENCES.md`.

## 2. Simuler l'entraînement (cette nuit)
```powershell
backend\.venv\Scripts\python -m training.train_lora --simulate --run-id essai1 --budget-hours 3
```
Options de panne : `--sim-nan-at N`, `--sim-kill-at N` (puis relancer avec le même `--run-id` : reprise),
`--sim-disk-full-at N`, `--sim-hot-at N`, `--sim-plateau-at N`. Codes de sortie : 0 fini · 3 budget · 4 arrêt propre · 5 export · 6 données.

## 3. Garde-fous (08 §7.3)
1. Mesure de 50 pas → durée estimée → refus si > `--budget-hours` (aucun long calcul lancé).
2. Essai sur 1 % des pas + **export test** (adaptateur → GGUF → Modelfile `ADAPTER`) avant le long entraînement.
3. Point de reprise toutes les `--save-every-min` min (3 gardés, marqueur `COMPLETE` écrit en dernier), reprise automatique.
4. Arrêt propre + point de reprise : perte NaN/inf ou > 3× la perte initiale, disque < `--min-free-gb`, GPU > `--max-gpu-temp`, Ctrl+C.
5. Journal `training/runs/<id>/run.json` : versions, matériel, graine, paramètres, empreintes SHA-256, phases, métriques, durée.
6. Profils : `colab` (**données publiques/synthétiques uniquement**, refus sinon) et `pc-nuit`.

## 4. Installation réelle (plus tard, avec l'utilisateur)
```powershell
backend\.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu121   # CUDA à adapter
backend\.venv\Scripts\python -m pip install -r training\requirements-train.txt
```
Puis enlever `--simulate`. Le moteur `TorchBackend` (train_lora.py) n'a **jamais été exécuté** : il faut le
valider sur le GPU (essai 1 % d'abord). Export réel : cloner llama.cpp, `set LLAMA_CPP_DIR=...`, passer `--base-model-dir`
dans `export_gguf.py`, puis `ollama create cadrage-lora -f <export>/Modelfile`.
Tests : `backend\.venv\Scripts\python -m pytest training/tests -q`.

## Entraîner Qwen3-4B sur Colab (`training/colab/cadrage_entrainement.ipynb`)
C'est **un seul** entraînement QLoRA 4 bits, en 2 parties qui reprennent depuis ton Google Drive. Colab est un cloud :
`training/parts.py` refuse tout exemple qui n'est pas public sous licence ouverte (CC BY, Licence Ouverte, décision 2011/833/UE).

**Paquet v5 (24/11)** : paquet v4 (535 exemples) + tâche **« axes »** (140 exemples : 100 / 4 / 36), avec le MÊME découpage par rapport. Vérité : le sommaire de chaque rapport de la Cour (grandes parties des observations et leurs plages de points) ; un constat recopié du point N appartient à la partie dont la plage contient N ; titres recopiés. Les constats sont mélangés : l'ordre de la liste ne dit rien de l'axe. Format : axes nouveaux déclarés une fois (`new_axes`, A1 : titre), puis une ligne par constat (`assignments`, F → A). Reconstruire : `python -m training.dataset.add_axes --v4 <paquet v4> --eca-dir DOSSIER --out-dir SORTIE`. Test : paires de constats bien rangées (ensemble ou séparés) comme dans le sommaire.

**Données** : `training/colab/cadrage-donnees-publiques.zip` (SHA-256 écrit dans le carnet et vérifié avant tout calcul) =
pilote v2 relu (28 exemples) + pilote v3 (25), soit 53 : 33 en entraînement, 7 en validation, 13 en test, séparés
PAR DOCUMENT SOURCE. Les invites v2 sont refaites avec les fonctions actuelles de l'application ; deux exemples v2 (sections
« Profil » et « Calendrier » des TdR, que l'application rend sans modèle depuis les décisions humaines) sont écartés.
Reconstruire : `python -m training.dataset.assemble --v2 pilote-30-relu.jsonl --sources-dir DOSSIER --out-dir SORTIE`.

**Réglages** (`profiles/colab-parties.yaml`) : base `Qwen/Qwen3-4B` (révision épinglée), r = 16, 3 époques, taux 1e-4,
validation toutes les 4 pas, arrêt après 2 mesures de suite au-dessus de la meilleure ; l'export prend la MEILLEURE sauvegarde.

**Invite** : celle d'Ollama pour `qwen3:4b` (`render_prompt`) : pas de « /no_think », une ligne vide APRÈS le texte système, la
balise `<think>` reste ouverte et la réponse (JSON) commence juste après. Relevé sur Ollama 0.40.17 (`_debug_render_only`) ;
revérifié à la partie 0.

**Export** (même chaîne pour la base et la base + LoRA) : fusion → GGUF f16 → `llama-quantize` **Q4_K_M** (compilé dans Colab) →
Modelfile (gabarit et paramètres de qwen3:4b, `training/ollama/qwen3-4b.Modelfile`) → SHA-256. Sur Drive :
`cadrage-entrainement/etat-4b/modeles/{cadrage-4b-lora,cadrage-4b-base}/model.gguf` + `SHA256SUMS.txt`.

**Côté PC** : `python -m training.import_ollama --lora <dossier>/cadrage-4b-lora --base <dossier>/cadrage-4b-base --sums SHA256SUMS.txt`
vérifie les empreintes et le gabarit, crée `cadrage-4b-base` et `cadrage-4b-lora`, relit leur empreinte dans Ollama et fait une
réponse de contrôle. Puis, dans `backend/` : `python -m eval.harness.run --config eval/configs/B-4b-base.yaml` et `C-4b-lora.yaml`
(porte de pertinence à 0,45, mêmes graines).

À savoir :
- Ollama 0.40 refuse les adaptateurs LoRA : on livre un GGUF complet.
- Le gabarit Hugging Face de Qwen3 n'est pas celui d'Ollama : l'invite vient de `render_prompt`.
- Rien n'a encore tourné sur Colab : le carnet est testé en simulation seulement (`pytest training`).

## Kaggle (quota Colab épuisé)

`training/kaggle/cadrage_entrainement_kaggle.ipynb` est fabriqué par `training/kaggle/make_notebook_kaggle.py` à partir du carnet Colab :
mêmes étapes, mêmes versions épinglées (`CODE`, `DONNEES`, llama.cpp, Ollama, révision de Qwen3-4B), même test par tâche en dernière cellule.
Différences : stockage dans `/kaggle/working/cadrage-entrainement` (au lieu de Drive), fichiers temporaires dans `/kaggle/temp`,
un seul GPU (`CUDA_VISIBLE_DEVICES=0`), reprise depuis un « Input » (version enregistrée). Rien n'a encore tourné sur Kaggle.
