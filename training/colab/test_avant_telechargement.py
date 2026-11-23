#@title Test avant téléchargement : base contre LoRA, par type de tâche (20 à 60 min) {display-mode: "form"}
# À lancer APRÈS les deux exports. Rien n'est téléchargé : les deux modèles sont déjà dans l'Ollama de Colab.
# Les exemples de test viennent de rapports jamais vus à l'entraînement. Mesure par type de tâche (meta.task_type) :
# JSON valide, bonne décision (répondre ou refuser), phrases vérifiées par le vérificateur de l'application,
# et pour les tâches « position » et « conflit », étiquette (accept / partial / reject ; conflict / aligned) notée
# comme une classification contre la position officielle de la Commission.
import json, re, sys, time, urllib.request, zipfile
from collections import Counter, defaultdict
sh(f"{sys.executable} -m pip install -q snowballstemmer pydantic")
sys.path.insert(0, "/content/cadrage/backend")
from app.domain.documents import Chunk
from app.domain.generation import SectionDraft, Sentence
from app.generation.llm_schemas import LLMFindings, LLMSection, LLMStance
from app.verification import verify_section

z = zipfile.ZipFile(STOCK / "cadrage-donnees-publiques.zip")
nom = next(n for n in z.namelist() if n.endswith("test.jsonl"))
tests = [json.loads(l) for l in z.read(nom).decode("utf-8").splitlines() if l.strip()]
TACHES = sorted({e["meta"].get("task_type", "autre") for e in tests})
print(f"{len(tests)} exemples de test :", dict(Counter(e["meta"].get("task_type", "autre") for e in tests)))

def schema_de(ex):
    t = ex["meta"]["rendu"]["tache"]
    return LLMFindings if t == "constats" else LLMStance if t in ("position", "conflict") else LLMSection

def demander(modele, messages, schema):
    corps = {"model": modele, "messages": messages, "stream": False, "think": False,
             "format": schema.model_json_schema(), "truncate": False, "shift": False,
             "options": {"temperature": 0, "num_ctx": 4096}}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", json.dumps(corps).encode(),
                                 {"Content-Type": "application/json"})
    t = time.time()
    r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    return r["message"]["content"], time.time() - t

def noter(ex, texte):
    passages = dict(re.findall(r"<<PASSAGE id=(P\d+)[^>]*>>\n(.*?)\n<<FIN", ex["messages"][1]["content"], re.S))
    attendu = json.loads(ex["messages"][2]["content"])
    try:
        sortie = json.loads(texte)
    except ValueError:
        return {"json": 0}
    constats = "findings" in attendu
    phrases = sortie.get("findings" if constats else "sentences") or []
    refus_attendu = attendu.get("status") == "insufficient_evidence"
    refus = sortie.get("status") == "insufficient_evidence" or not phrases
    chunks = {l: Chunk(id=l, document_id="d", dossier_id="d", ordinal=0, text=t, page_start=1, page_end=1,
                       section_path=(), token_estimate=1) for l, t in passages.items()}
    ss = [Sentence(text=p.get("text", ""), kind=p.get("kind", "fact"),
                   source_ids=[re.sub(r"\W", "", s).upper() for s in p.get("sources", [])]) for p in phrases]
    rep = verify_section(SectionDraft(section_key="t", status="ok", sentences=ss), chunks, dossier_id="d")
    note = {"json": 1, "statut_juste": int(refus == refus_attendu), "phrases": len(ss),
            "verifiees": sum(c.status == "verified" for c in rep.checks),
            "bloquantes": sum(i.severity == "blocking" for i in rep.issues),
            "francais": int(all(not re.search(r"\b(the|and|of|with)\b", s.text) for s in ss))}
    if ex["meta"].get("etiquette"):  # position / conflit : classification
        note["etiquette_juste"] = int(sortie.get("stance") == ex["meta"]["etiquette"])
        note["etiquette_n"] = 1
        note["conf"] = f'{ex["meta"]["etiquette"]}->{sortie.get("stance")}'
    return note

resultats, confusions = {}, defaultdict(Counter)
for modele in ("cadrage-4b-base", "cadrage-4b-lora"):
    par_tache, temps = defaultdict(Counter), 0.0
    for i, ex in enumerate(tests, 1):
        texte, s = demander(modele, ex["messages"][:2], schema_de(ex))
        note = noter(ex, texte)
        tache = ex["meta"].get("task_type", "autre")
        par_tache[tache].update({k: v for k, v in note.items() if isinstance(v, int)})
        par_tache[tache]["n"] += 1
        if "conf" in note:
            confusions[modele][note["conf"]] += 1
        temps += s
        print(f"{modele} {i}/{len(tests)} {tache} {note}")
    resultats[modele] = (par_tache, temps)

print("\n================ RÉSUMÉ PAR TÂCHE (à envoyer à Claude) ================")
for modele, (par_tache, temps) in resultats.items():
    print(f"\n### {modele} ({temps / len(tests):.0f} s par exemple)")
    total = Counter()
    for tache in TACHES:
        t = par_tache[tache]
        total.update(t)
        et = f" | étiquette juste {t['etiquette_juste']}/{t['etiquette_n']}" if t["etiquette_n"] else ""
        print(f"{tache:18s} n={t['n']:3d} | JSON {t['json']}/{t['n']} | statut juste {t['statut_juste']}/{t['n']} | "
              f"phrases vérifiées {t['verifiees']}/{t['phrases']} | bloquantes {t['bloquantes']}{et}")
    print(f"{'TOTAL':18s} n={total['n']:3d} | JSON {total['json']}/{total['n']} | statut juste {total['statut_juste']}/{total['n']} | "
          f"phrases vérifiées {total['verifiees']}/{total['phrases']} | bloquantes {total['bloquantes']} | "
          f"tout en français {total['francais']}/{total['n']}")
    if confusions[modele]:
        print("confusions (attendu->obtenu) :", dict(confusions[modele]))

ex = tests[0]
print("\n================ EXEMPLE : même question, deux modèles ================")
for modele in resultats:
    print(f"\n--- {modele}\n", demander(modele, ex["messages"][:2], schema_de(ex))[0][:1500])
print("\n--- réponse humaine attendue\n", ex["messages"][2]["content"][:1500])
