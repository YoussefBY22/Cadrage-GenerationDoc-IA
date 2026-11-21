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
