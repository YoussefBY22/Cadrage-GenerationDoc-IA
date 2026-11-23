"""Fabrique le carnet Kaggle à partir du carnet Colab (mêmes étapes, mêmes versions épinglées, même test).

    python training/kaggle/make_notebook_kaggle.py training/colab/cadrage_entrainement.ipynb \
        training/kaggle/cadrage_entrainement_kaggle.ipynb

Ce qui change : pas de Google Drive (stockage dans /kaggle/working), fichiers temporaires dans /kaggle/temp
(hors des 20 Go de /kaggle/working), un seul GPU, reprise depuis la version enregistrée d'une session précédente.
"""

import json
import sys

SRC, OUT = sys.argv[1], sys.argv[2]
nb = json.load(open(SRC, encoding="utf-8"))
cells = nb["cells"]


def src(cell) -> str:
    return "".join(cell["source"])


def put(cell, text: str) -> None:
    cell["source"] = text.strip("\n").splitlines(True)


INTRO = """
# Cadrage : entraîner la LoRA de Qwen3-4B sur Kaggle

Tu vas entraîner un petit « supplément » (une LoRA) sur environ 340 exemples publics (rapports de la Cour des comptes
européenne et pièces de marché), puis fabriquer **deux modèles** pour Ollama, passés par exactement la même chaîne :
la **base** et la **base + LoRA**. La LoRA apprend le **format**, la citation, le refus, la position et le conflit.
Elle n'apprend aucun fait de client. Aucun mot de passe ni jeton n'est demandé dans ce carnet.

## Avant de commencer (une seule fois)
1. Compte Kaggle **vérifié par téléphone** (Paramètres du compte → Phone verification) : sans cela, l'accès Internet et le GPU sont refusés.
2. Dans le carnet, panneau de droite **Session options** :
   - **Accelerator** : **GPU T4 x2** (le carnet n'en utilise qu'un) ou **GPU P100**. T4 est recommandé ;
   - **Internet** : **On** (le code et les données sont téléchargés depuis GitHub, les bibliothèques et le modèle depuis Internet) ;
   - **Persistence** : **Files only** (les fichiers de `/kaggle/working` survivent aux sessions enregistrées).
3. **Quota** : ton quota GPU hebdomadaire est affiché dans ton profil (Settings, ou sous ton avatar : « GPU hours »).
   Il faut environ **3 à 4 heures** de GPU pour tout faire (estimation, rien n'a encore tourné sur Kaggle). Vérifie-le avant de commencer.

## Comment lancer
Lance les cellules **une par une, dans l'ordre** (pas « Run All »). Chaque titre dit l'étape et sa durée estimée.
Toute la préparation et l'entraînement tiennent en **une seule session** (jusqu'à 12 h).

| Étape | Durée estimée |
|---|---|
| 1 à 7 : préparer | 20 à 30 min |
| Partie 0 : preuve | 15 à 25 min |
| Parties 1, 2 et 3 : entraînement | 1 h 30 à 3 h en tout (non mesuré) |
| Exporter le modèle entraîné, puis la base | 20 à 30 min chacun |
| Résumé | 1 min |
| Test avant téléchargement : base contre LoRA, par tâche | 40 à 80 min |

## Si la session coupe
Tout est sauvegardé dans `/kaggle/working/cadrage-entrainement` au fur et à mesure. Avec **Persistence : Files only**
(session options), Kaggle garde les fichiers de `/kaggle/working` quand la session s'arrête et les remet à la reprise du carnet.
Pour reprendre : rouvre le carnet, relance les étapes 1 à 7, puis la **même** partie : elle reprend où elle s'était arrêtée.
**Sécurité en plus** (à vérifier par toi, rien n'a encore tourné sur Kaggle) : après la partie 0 et après chaque partie,
fais **Save Version → Quick Save** (il n'écrase rien et ne relance rien). **N'utilise pas « Save & Run All »** : il relancerait tout depuis le début.
Si la persistance n'a pas marché : **Add Input** → ton propre carnet (« Your Work »), sa dernière version enregistrée,
puis relance les étapes 1 à 7 : l'étape 1 recopie l'état trouvé dans cet Input.

## À la fin
Lis le **résumé du test** (dernière cellule). Télécharge les modèles **seulement si le modèle entraîné fait mieux que la base**
sur les tâches qui comptent. Où : panneau de droite **Output** (liste des fichiers de `/kaggle/working`), dossier
`cadrage-entrainement/etat-4b/modeles`. Fichiers : `cadrage-4b-lora/model.gguf` + `.sha256`, `cadrage-4b-base/model.gguf` + `.sha256`
et `SHA256SUMS.txt`. Puis sur ton PC :
`python -m training.import_ollama --lora <dossier>/cadrage-4b-lora --base <dossier>/cadrage-4b-base --sums <dossier>/SHA256SUMS.txt`.
Données : uniquement des documents publics (CC BY 4.0, Licence Ouverte 2.0). **Jamais de document client.**
"""

STEP1_HEAD = src(cells[1]).split("\n")
# constantes épinglées du carnet Colab (CODE, LLAMA, DONNEES, OLLAMA, BASE_REVISION) : on les recopie telles quelles
consts = [ln for ln in STEP1_HEAD if ln.startswith(("CODE = ", "LLAMA = ", "DONNEES = ", "OLLAMA = ", "BASE_REVISION = "))]
sh_def = src(cells[1])[src(cells[1]).index("def sh(commande):"):src(cells[1]).index("if subprocess.run(\"nvidia-smi\"")]

STEP1 = f'''
#@title Étape 1 sur 7 : vérifier le GPU, Internet et le stockage (1 min) {{display-mode: "form"}}
import hashlib, os, shutil, signal, subprocess, sys, time, urllib.request, zipfile
from pathlib import Path

{chr(10).join(consts)}

{sh_def}
if subprocess.run("nvidia-smi", shell=True, capture_output=True).returncode:
    raise RuntimeError("Pas de GPU. Panneau de droite, Session options, Accelerator : GPU T4 ou P100, puis relance.")
GPUS = sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader").strip().splitlines()
print("GPU :", " | ".join(GPUS))
os.environ["CUDA_VISIBLE_DEVICES"] = "0"   # un seul GPU : plus simple et plus sûr (T4 x2 : le second reste inutilisé)
nom = GPUS[0].lower()
if "p100" in nom:
    print("P100 détectée : fp16 comme sur T4 ; la partie 0 vérifie que l'entraînement 4 bits y fonctionne (non vérifié ici).")
elif "t4" not in nom:
    print("GPU inattendu :", GPUS[0], "- la partie 0 dira si tout fonctionne.")
try:
    urllib.request.urlopen("https://raw.githubusercontent.com", timeout=15)
except OSError:
    raise RuntimeError("Pas d'accès Internet. Panneau de droite, Session options, Internet : On (compte vérifié par téléphone), puis relance.")

# Fichiers temporaires (code, llama.cpp, modèle de base, Ollama) hors des 20 Go de /kaggle/working.
os.makedirs("/kaggle/temp/hf", exist_ok=True)
os.makedirs("/kaggle/temp/ollama", exist_ok=True)
os.environ["HF_HOME"] = "/kaggle/temp/hf"
os.environ["OLLAMA_MODELS"] = "/kaggle/temp/ollama"
STOCK = Path("/kaggle/working/cadrage-entrainement")   # état d'entraînement et modèles finis : à conserver (Quick Save)
STOCK.mkdir(parents=True, exist_ok=True)
if not any(STOCK.iterdir()):  # reprise : état d'une version enregistrée, ajouté comme « Input »
    for ancien in sorted(Path("/kaggle/input").glob("*/cadrage-entrainement")) + sorted(Path("/kaggle/input").glob("*/*/cadrage-entrainement")):
        shutil.copytree(ancien, STOCK, dirs_exist_ok=True)
        print("Reprise : état recopié depuis", ancien)
        break
libre = shutil.disk_usage("/kaggle/working").free / 1e9
print(f"Place libre dans /kaggle/working : {{libre:.0f}} Go (limite Kaggle : 20 Go ; il en faut environ 8).")
if libre < 8:
    raise RuntimeError("Pas assez de place dans /kaggle/working (8 Go minimum). Supprime d'anciens fichiers Output puis relance.")
'''

new = [dict(cells[0])]
put(new[0], INTRO)
for i, cell in enumerate(cells[1:], 1):
    cell = json.loads(json.dumps(cell))  # copie
    if i == 1:
        put(cell, STEP1)
    elif cell["cell_type"] == "code":
        t = src(cell).replace("/content", "/kaggle/temp")
        t = t.replace("Si Colab coupe", "Si Kaggle coupe").replace("nouvelle session Colab", "nouvelle session Kaggle")
        t = t.replace("sur Drive", "dans /kaggle/working").replace("l'Ollama de Colab", "l'Ollama de Kaggle")
        t = t.replace("ton Drive", "/kaggle/working (Quick Save)").replace("dossier cadrage-entrainement/etat-4b/modeles",
                                                                       "dossier cadrage-entrainement/etat-4b/modeles (onglet Output)")
        put(cell, t)
    new.append(cell)

# l'étape « Ollama » : démarre le serveur avec OLLAMA_MODELS déjà dans l'environnement ; rien d'autre à changer
nb["cells"] = new
nb["metadata"]["accelerator"] = "GPU"
nb["metadata"]["kaggle"] = {"accelerator": "gpu", "isInternetEnabled": True, "language": "python", "sourceType": "notebook"}
nb["metadata"].pop("colab", None)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
    f.write("\n")
print("ok", len(new))
