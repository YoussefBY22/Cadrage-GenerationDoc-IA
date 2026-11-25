import json
import sys

CODE, DONNEES = sys.argv[1], sys.argv[2]
OUT = sys.argv[3]

cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)})


def code(text):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                  "source": text.strip("\n").splitlines(True)})


md("""
# Cadrage : entraîner la LoRA de Qwen3-4B

Tu vas entraîner un petit « supplément » (une LoRA) sur environ 340 exemples publics (rapports de la Cour des comptes européenne et pièces de marché), puis fabriquer
**deux modèles** pour Ollama, passés par exactement la même chaîne : la **base** et la **base + LoRA**.
La LoRA apprend le **format**, la citation et le refus. Elle n'apprend aucun fait de client.

**Avant tout :** menu **Exécution → Modifier le type d'exécution → T4 GPU → Enregistrer**.

Lance les cellules **une par une, dans l'ordre** (pas « Tout exécuter »). Chaque titre dit l'étape et sa durée
estimée (estimations, rien n'a encore tourné sur Colab).

| Étape | Durée estimée |
|---|---|
| 1 à 7 : préparer (à refaire à chaque nouvelle session Colab) | 20 à 30 min |
| Partie 0 : preuve | 15 à 25 min |
| Parties 1, 2 et 3 : entraînement | 1 h 30 à 3 h en tout (non mesuré) |
| Exporter le modèle entraîné, puis la base | 20 à 30 min chacun |
| Résumé | 1 min |
| Test avant téléchargement : base contre LoRA, par tâche | 40 à 80 min |

Si Colab coupe : relance les étapes 1 à 7, puis la **même** partie. Tout est sauvegardé sur ton Drive.
Aucun mot de passe ni jeton n'est demandé : tu autorises seulement l'accès à ton Drive quand Colab le propose.
Données : uniquement des documents publics (CC BY 4.0, Licence Ouverte 2.0). **Jamais de document client.**
""")

code(f'''
#@title Étape 1 sur 7 : brancher le GPU et ton Google Drive (1 min) {{display-mode: "form"}}
import hashlib, os, shutil, signal, subprocess, sys, time, urllib.request, zipfile
from pathlib import Path

CODE = "{CODE}"            # version exacte du code
LLAMA = "e300919cc704ddde3a8a8346a8714f57eeeee71b"   # version exacte de llama.cpp
DONNEES = "{DONNEES}"      # empreinte SHA-256 du paquet de données publiques
OLLAMA = "0.40.17"         # la même version que sur le PC
BASE_REVISION = "1cfa9a7208912126459214e8b04321603b3df60c"   # Qwen/Qwen3-4B, révision épinglée

def sh(commande):
    r = subprocess.run(["bash", "-c", "set -o pipefail; " + commande], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"Échec : {{commande}}\\n{{(r.stderr or r.stdout)[-1500:]}}")
    return r.stdout

if subprocess.run("nvidia-smi", shell=True, capture_output=True).returncode:
    raise RuntimeError("Pas de GPU. Menu Exécution, Modifier le type d'exécution, T4 GPU, puis relance.")
print("GPU :", sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader").strip())

from google.colab import drive
drive.mount("/content/drive")
STOCK = Path("/content/drive/MyDrive/cadrage-entrainement")
STOCK.mkdir(parents=True, exist_ok=True)
libre = shutil.disk_usage("/content/drive/MyDrive").free / 1e9
print(f"Drive branché. Place libre : {{libre:.0f}} Go (il en faut environ 8).")
if libre < 8:
    raise RuntimeError("Pas assez de place sur ton Drive (8 Go minimum). Fais de la place puis relance.")
''')

code('''
#@title Étape 2 sur 7 : récupérer le code et les données publiques, avec vérification (2 min) {display-mode: "form"}
GITHUB = "https://github.com/YoussefBY22/PRV-PR8-PFE-IA-Cadrage"
RAW = "https://raw.githubusercontent.com/YoussefBY22/PRV-PR8-PFE-IA-Cadrage"

contenu = urllib.request.urlopen(f"{RAW}/{CODE}/training/colab/cadrage-donnees-publiques.zip", timeout=120).read()
if hashlib.sha256(contenu).hexdigest() != DONNEES:
    raise RuntimeError("Le paquet de données ne correspond pas à l'empreinte attendue : n'entraîne pas, préviens Claude.")
ARCHIVE = STOCK / "cadrage-donnees-publiques.zip"
ARCHIVE.write_bytes(contenu)
print("Paquet de données vérifié (SHA-256 identique) :", DONNEES[:16], "...")

os.chdir("/content")
REPO = Path("/content/cadrage")
sh(f"rm -rf {REPO} && git init -q {REPO} && git -C {REPO} fetch -q --depth 1 {GITHUB}.git {CODE} && git -C {REPO} checkout -q FETCH_HEAD")
zipfile.ZipFile(ARCHIVE).extractall(REPO / "training/data/real")
import json
m = json.loads((REPO / "training/data/real/MANIFEST.json").read_text(encoding="utf-8"))
for part in ("train", "val", "test"):
    e = m["effectifs"][part]
    print(f"{part:5s} : {e['exemples']:2d} exemples, {e['documents']} documents")
print("Licences :", " ; ".join(m["licences"]))
''')

code('''
#@title Étape 3 sur 7 : installer les bibliothèques d'entraînement (3 min) {display-mode: "form"}
sh(f"{sys.executable} -m pip install -q transformers==4.57.6 peft==0.17.1 accelerate==1.10.1 "
   "bitsandbytes==0.50.2 huggingface_hub==0.36.2 sentencepiece pyyaml")
print("Bibliothèques installées.")
''')

code('''
#@title Étape 4 sur 7 : télécharger Qwen3-4B, version épinglée (8 Go, 5 à 10 min) {display-mode: "form"}
BASE = sh(f"""{sys.executable} -c 'from huggingface_hub import snapshot_download as d; """
          f"""print(d("Qwen/Qwen3-4B", revision="{BASE_REVISION}"))'""").strip().splitlines()[-1]
print("Modèle de base prêt :", BASE)
''')

code('''
#@title Étape 5 sur 7 : installer Ollama et vérifier le gabarit de qwen3:4b (5 min) {display-mode: "form"}
if not shutil.which("ollama"):
    sh("apt-get install -y -qq zstd")
    sh(f"curl -fsSL https://ollama.com/install.sh | OLLAMA_VERSION={OLLAMA} sh")
def ollama_pret():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=2)
        return True
    except OSError:
        return False
if not ollama_pret():
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(60):
        if ollama_pret():
            break
        time.sleep(1)
sh("ollama pull qwen3:4b")
print(sh(f"cd {REPO} && {sys.executable} -c 'from training import export_gguf as e; e.check_template(); print(\\"Gabarit de qwen3:4b identique à celui du dépôt.\\")'").strip())
''')

code('''
#@title Étape 6 sur 7 : compiler l'outil de quantification de llama.cpp (5 min) {display-mode: "form"}
sh("rm -rf /content/llama.cpp && git init -q /content/llama.cpp && git -C /content/llama.cpp fetch -q --depth 1 "
   f"https://github.com/ggml-org/llama.cpp.git {LLAMA} && git -C /content/llama.cpp checkout -q FETCH_HEAD")
sh(f"{sys.executable} -m pip install -q numpy sentencepiece protobuf")
print(sh(f"cd {REPO} && {sys.executable} -c 'from pathlib import Path; from training import export_gguf as e; print(e.build_quantize(Path(\\"/content/llama.cpp\\")))'").strip())
''')

code('''
#@title Étape 7 sur 7 : outil de lancement (instantané) {display-mode: "form"}
def cadrage(*action):
    env = dict(os.environ, LLAMA_CPP_DIR="/content/llama.cpp", PYTHONUNBUFFERED="1",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    cmd = [sys.executable, "-m", "training.parts", *map(str, action),
           "--store", str(STOCK / "etat-4b"), "--base-dir", BASE]
    p = subprocess.Popen(cmd, cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors="replace", start_new_session=True)
    try:
        for ligne in p.stdout:
            print(ligne, end="")
    except KeyboardInterrupt:
        print("Arrêt demandé : sauvegarde en cours, attends le message de fin.")
        p.send_signal(signal.SIGINT)
        for ligne in p.stdout:
            print(ligne, end="")
    code = p.wait()
    os.sync()
    if code:
        raise RuntimeError(f"Non terminé (code {code}). Copie ce qui est affiché au-dessus à Claude.")

cadrage("etat")
print("PRÊT. Tu peux lancer la partie 0.")
''')

code('''
#@title Partie 0 : preuve que tout fonctionne (15 à 25 min, obligatoire) {display-mode: "form"}
# 2 pas d'entraînement, sauvegarde, reprise, export complet (GGUF Q4_K_M) et réponse d'Ollama.
# Si elle échoue : ne va pas plus loin, copie le message à Claude.
cadrage("preuve")
''')

code('''
#@title Partie 1 : entraînement, premier tiers (30 à 60 min) {display-mode: "form"}
# Si Colab coupe : relance les étapes 1 à 7 puis CETTE cellule : elle reprend où elle s'était arrêtée.
cadrage("partie", 1)
''')

code('''
#@title Partie 2 : entraînement, deuxième tiers (30 à 60 min) {display-mode: "form"}
# Si l'erreur de validation remontait déjà (arrêt anticipé), cette cellule le dit et ne fait rien : c'est normal.
cadrage("partie", 2)
''')

code('''
#@title Partie 3 : entraînement, dernière partie (30 à 60 min) {display-mode: "form"}
# Si l'erreur de validation remontait déjà (arrêt anticipé), cette cellule le dit et ne fait rien : c'est normal.
cadrage("partie", 3)
''')

code('''
#@title Où j'en suis (instantané, à lancer quand tu veux) {display-mode: "form"}
cadrage("etat")
''')

code('''
#@title Exporter le modèle entraîné : fusion, GGUF, Q4_K_M, SHA-256 (15 à 30 min, 2,5 Go sur Drive) {display-mode: "form"}
cadrage("exporter")
''')

code('''
#@title Exporter la base Qwen3-4B par la MÊME chaîne, pour comparer honnêtement (15 à 30 min, 2,5 Go) {display-mode: "form"}
cadrage("exporter-base")
''')

code('''
#@title Résumé : pas, pertes, durée, fichiers à télécharger (instantané) {display-mode: "form"}
cadrage("resume")
print()
print("TÉLÉCHARGE depuis ton Drive, dossier cadrage-entrainement/etat-4b/modeles :")
print("  cadrage-4b-lora/model.gguf et cadrage-4b-lora/model.gguf.sha256")
print("  cadrage-4b-base/model.gguf et cadrage-4b-base/model.gguf.sha256")
print("  SHA256SUMS.txt")
print("Puis, sur ton PC : python -m training.import_ollama --lora <dossier>/cadrage-4b-lora --base <dossier>/cadrage-4b-base")
''')

cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
              "source": open(sys.argv[4], encoding="utf-8").read().strip(chr(10)).splitlines(True)})

nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                                   "language_info": {"name": "python"}, "colab": {"provenance": []},
                                   "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
    f.write("\n")
print("ok", len(cells))
