"""Pilote v3 : 5 exemples par type, sorties humaines réelles, invite rendue par l'application.

Chaque exemple suit le format de ``pilote-30-relu.jsonl`` : ``messages`` (système, utilisateur, assistant) et
``meta``. L'invite est produite par ``app.generation.prompting`` (la même fonction que l'inférence) ; la
réponse est du JSON ``LLMSection`` ou ``LLMFindings``. Chaque exemple passe le vérificateur de l'application.

Usage :
    python -m training.dataset.v3_sources --sources-dir DOSSIER --fetch
    python -m training.dataset.v3_build --sources-dir DOSSIER --out-dir training/data/pilote-v3
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import statistics
from pathlib import Path

from app.domain.documents import Chunk
from app.domain.retrieval import Passage
from app.generation import prompting
from app.generation.llm_schemas import LLMFindings, LLMSection
from app.generation.template_loader import SectionSpec, load_template
from app.verification import resolve_labels, verify_section

from training.dataset import v3_curation
from training.dataset.v3_sources import SOURCES, check_manifest, source_text
from training.dataset.v3_text import between, flat

SEED = 23
LANG = "fr"
TYPES = ["feuille de route", "termes de référence", "cahier des charges",
         "divergence entre deux sources", "extraction de constats"]
TPL_FILES = {"roadmap": "roadmap", "tor": "tor", "cdc": "cdc"}
_PAREN = re.compile(r"\s*\((?:voir )?points? [^)]*\)")


class CurationError(ValueError):
    """Un repère, une phrase ou un document ne correspond pas à la source."""


def section_spec(section: tuple) -> SectionSpec:
    """Gabarit de l'application (``backend/app/generation/templates``) ou consigne libre écrite par l'assistant."""
    if section[0] == "custom":
        _, title, instructions = section
        return SectionSpec(key="divergences", title=title, instructions=instructions,
                           queries=[title, "points de désaccord"], max_sentences=6, min_sources=2)
    kind, key = section
    for s_ in load_template(kind, LANG).sections:
        if s_.key == key:
            if s_.requires_decisions:  # l'application la rend depuis les décisions humaines, sans modèle
                raise CurationError(f"{section} exige des décisions : l'application n'envoie pas cette section au modèle")
            return s_
    raise CurationError(f"section inconnue : {section}")


def _clean_sentence(s: str) -> str:
    return flat(_PAREN.sub("", s)).rstrip(" .;,:")


def contains(passage: str, sentence: str) -> bool:
    """La phrase est recopiée dans le passage (apostrophes et renvois « voir points » mis à part)."""
    return _clean_sentence(sentence) in _clean_sentence(passage) or _clean_sentence(sentence) in flat(passage)


def assemble(amorce: str, item: str, sep: str = " ") -> str:
    """Amorce + alinéa en une phrase ; ``sep`` ajoute au besoin une virgule (seule retouche du texte)."""
    a, i = amorce.strip().rstrip(" :;,"), item.strip().rstrip(" ;.,")
    return f"{a}{sep}{i}."


def read_passages(ex: dict, texts: dict[str, str]) -> list[str]:
    out = []
    for p in ex["passages"]:
        if p["doc"] != ex["doc"]:
            raise CurationError(f"{ex['id']} : un exemple n'utilise qu'un document source")
        try:
            out.append(between(texts[p["doc"]], p["start"], p["end"], include_end=p["incl"], after=p["after"]))
        except ValueError as e:
            raise CurationError(f"{ex['id']} : {e}") from e
    return out


def output_sentences(ex: dict, passages: list[str]) -> list[dict]:
    """Phrases de sortie : texte, rang du passage, origine (recopiée ou assemblée), kind."""
    res: list[dict] = []
    for ph in ex.get("phrases", []):
        if ph[0] == "v":
            _, p, text = ph
            if not contains(passages[p], text):
                raise CurationError(f"{ex['id']} : phrase absente du passage {p} : {text[:70]!r}")
            res.append({"text": text, "src": p, "origine": "recopiée", "kind": "fact"})
        else:
            p, amorce, item = ph[1], ph[2], ph[3]
            sep = ph[4] if len(ph) > 4 else " "
            for part in (amorce, item):
                if not contains(passages[p], part):
                    raise CurationError(f"{ex['id']} : morceau absent du passage {p} : {part[:70]!r}")
            res.append({"text": assemble(amorce, item, sep), "src": p, "origine": "assemblée (amorce + alinéa)",
                        "kind": "recommendation"})
    for p, text, theme, sev in ((c[0], c[1], c[2], c[3]) for c in ex.get("constats", [])):
        if not contains(passages[p], text):
            raise CurationError(f"{ex['id']} : constat absent du passage {p} : {text[:70]!r}")
        res.append({"text": text.strip(), "src": p, "origine": "recopiée", "kind": "fact",
                    "theme": theme, "gravite": sev})
    return res


def _chunk(doc: str, ex_id: str, ordinal: int, text: str, title: str) -> Chunk:
    return Chunk(id=f"{doc}-{ex_id}-c{ordinal}", document_id=doc, dossier_id=ex_id, ordinal=ordinal, text=text,
                 page_start=None, page_end=None, section_path=(title,),
                 token_estimate=prompting.estimate_tokens(text))


def render_user(spec: SectionSpec | None, passages: list[Passage], nonce: str) -> str:
    """Invite utilisateur exactement comme l'application (section, ou constats si ``spec`` est ``None``)."""
    if spec is None:
        return prompting.build_findings_prompt(passages, nonce=nonce, lang=LANG)
    return prompting.build_section_prompt(spec, passages, nonce=nonce, lang=LANG)


def build_example(ex: dict, texts: dict[str, str], rng: random.Random) -> dict:
    src = SOURCES[ex["doc"]]
    ptexts = read_passages(ex, texts)
    sents = output_sentences(ex, ptexts)
    findings = ex["section"][0] == "findings"
    spec = None if findings else section_spec(ex["section"])
    title = "Constats du diagnostic" if findings else spec.title
    order = list(range(len(ptexts)))
    rng.shuffle(order)
    label = {old: f"P{new}" for new, old in enumerate(order, 1)}
    chunks = [_chunk(ex["doc"], ex["id"], j, ptexts[old], title) for j, old in enumerate(order)]
    passages = [Passage(label=f"P{i}", chunk=c, score=1.0 / i, ranks={"bm25": i}) for i, c in enumerate(chunks, 1)]
    nonce = rng.randbytes(6).hex()
    user = render_user(spec, passages, nonce)
    if findings:
        answer = {"status": "ok", "findings": [{"text": s["text"], "theme": s["theme"], "severity": s["gravite"],
                                                "sources": [label[s["src"]]]} for s in sents]}
        LLMFindings.model_validate(answer)
        draft = LLMSection.model_validate({"status": "ok", "sentences": [
            {"text": s["text"], "kind": "fact", "sources": [label[s["src"]]], "findings": []} for s in sents]})
    else:
        answer = {"status": "ok", "missing_evidence": None, "sentences": [
            {"text": s["text"], "kind": s["kind"], "sources": [label[s["src"]]], "findings": []} for s in sents]}
        draft = LLMSection.model_validate(answer)
    rep = verify_section(resolve_labels(draft, passages, section_key=title),
                         {p.chunk.id: p.chunk for p in passages}, dossier_id=ex["id"])
    blocking = [i.code for i in rep.issues if i.severity == "blocking"]
    consigne_par = ("assistant" if ex["section"][0] == "custom" else
                    "gabarit de l'application" if not findings else "application (tâche constats)")
    sortie = ("texte humain de la source, recopié" +
              (" ; thème et gravité écrits par l'assistant" if findings else "") +
              (" ; assemblage mécanique amorce + alinéa pour : "
               + str(sum(s['origine'].startswith('assemblée') for s in sents)) + " phrase(s)"
               if any(s["origine"].startswith("assemblée") for s in sents) else ""))
    meta = {
        "id": ex["id"], "kind": ex["type"], "lang": "fr", "real": True, "source": ex["doc"],
        "source_titre": src["titre"], "source_url": src["url"], "licence": src["licence"],
        "licence_preuve": src["preuve_url"], "split": "test" if src["test"] else "train",
        "consigne_ecrite_par": consigne_par, "sortie_ecrite_par": sortie, "valide_par_humain": False,
        "tpv": rep.tpv, "bloquants": blocking,
        "rendu": {"nonce": nonce, "tache": "constats" if findings else "section",
                  "spec": spec.model_dump() if spec else None,
                  "spec_origine": ("constats" if findings else "libre" if ex["section"][0] == "custom"
                                   else f"gabarit:{ex['section'][0]}/{ex['section'][1]}"),
                  "passages": [{"label": p.label, "texte": p.chunk.text, "titre": title} for p in passages]},
    }
    messages = [{"role": "system", "content": prompting.system_prompt(LANG)},
                {"role": "user", "content": user},
                {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)}]
    review = {"id": ex["id"], "type": ex["type"], "doute": ex.get("doute", ""), "titre": title,
              "consigne": spec.instructions if spec else prompting._t(LANG)["task_findings"],
              "passages": [(f"P{j}", ptexts[old]) for j, old in enumerate(order, 1)],
              "phrases": [{**s, "label": label[s["src"]]} for s in sents], "src": src, "meta": meta}
    return {"messages": messages, "meta": meta, "review": review}


def verify_example(example: dict) -> tuple[float, list[str]]:
    """Repasse le vérificateur de l'application sur un exemple fini (passages et réponse du fichier)."""
    r = example["meta"]["rendu"]
    ps = [Passage(label=p["label"], chunk=_chunk(example["meta"]["source"], example["meta"]["id"], i, p["texte"], p["titre"]),
                  score=1.0 / (i + 1), ranks={"bm25": i + 1}) for i, p in enumerate(r["passages"])]
    answer = json.loads(example["messages"][2]["content"])
    if "findings" in answer:
        LLMFindings.model_validate(answer)
        draft = LLMSection.model_validate({"status": "ok", "sentences": [
            {"text": f["text"], "kind": "fact", "sources": f["sources"], "findings": []} for f in answer["findings"]]})
    else:
        draft = LLMSection.model_validate(answer)
    rep = verify_section(resolve_labels(draft, ps, section_key="verif"), {p.chunk.id: p.chunk for p in ps},
                         dossier_id=example["meta"]["id"])
    return rep.tpv, [i.code for i in rep.issues if i.severity == "blocking"]


def rerender(example: dict) -> str:
    """Reconstruit l'invite utilisateur depuis ``meta.rendu`` : doit être identique à celle du fichier."""
    r = example["meta"]["rendu"]
    spec = SectionSpec(**r["spec"]) if r["spec"] else None
    ps = [Passage(label=p["label"], chunk=_chunk(example["meta"]["source"], example["meta"]["id"], i, p["texte"], p["titre"]),
                  score=1.0 / (i + 1), ranks={"bm25": i + 1}) for i, p in enumerate(r["passages"])]
    return render_user(spec, ps, r["nonce"])


def build_all(texts: dict[str, str], seed: int = SEED) -> list[dict]:
    problems = check_manifest()
    if problems:
        raise ValueError("manifeste invalide : " + "; ".join(problems))
    rng = random.Random(seed)
    return [build_example(ex, texts, rng) for ex in v3_curation.EXAMPLES]


def check_split(examples: list[dict]) -> list[str]:
    """Aucun document source des deux côtés (entraînement et test)."""
    sides: dict[str, set[str]] = {"train": set(), "test": set()}
    for e in examples:
        sides[e["meta"]["split"]].add(e["meta"]["source"])
    return sorted(sides["train"] & sides["test"])


def statistics_of(examples: list[dict], hashes: dict[str, str] | None = None) -> dict:
    sents = [s for e in examples for s in e["review"]["phrases"]]
    toks = [len(e["messages"][0]["content"] + e["messages"][1]["content"]) // 4 for e in examples]
    by_type = {t: sum(e["meta"]["kind"] == t for e in examples) for t in TYPES}
    split = {s: sum(e["meta"]["split"] == s for e in examples) for s in ("train", "test")}
    return {
        "exemples": len(examples), "types": by_type, "split": split,
        "documents": {s: sorted({e["meta"]["source"] for e in examples if e["meta"]["split"] == s})
                      for s in ("train", "test")},
        "documents_des_deux_cotes": check_split(examples),
        "phrases": len(sents), "phrases_recopiees": sum(s["origine"] == "recopiée" for s in sents),
        "phrases_assemblees": sum(s["origine"].startswith("assemblée") for s in sents),
        "consigne_ecrite_par_assistant": sum(e["meta"]["consigne_ecrite_par"] == "assistant" for e in examples),
        "constats_theme_gravite_assistant": sum(e["meta"]["kind"] == "extraction de constats" for e in examples),
        "licences": sorted({e["meta"]["licence"] for e in examples}),
        "bloquants": {e["meta"]["id"]: e["meta"]["bloquants"] for e in examples if e["meta"]["bloquants"]},
        "tpv_sous_1": {e["meta"]["id"]: e["meta"]["tpv"] for e in examples if e["meta"]["tpv"] < 1},
        "entree_jetons_estimes": [min(toks), int(statistics.median(toks)), max(toks)],
        "mots_par_phrase_mediane": int(statistics.median(len(s["text"].split()) for s in sents)),
        "sha256_pdf": hashes or {},
    }


_CSS = """*{box-sizing:border-box}body{margin:0;background:#F6F6FA;color:#2E2E38;font:15px/1.5 "Segoe UI",system-ui,sans-serif}
main{max-width:1080px;margin:auto;padding:16px}
.top{position:sticky;top:0;z-index:2;background:#2E2E38;color:#fff;padding:10px 16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.top strong{color:#FFE600}.top button{margin-left:auto;background:#FFE600;border:0;padding:8px 14px;font:inherit;font-weight:600;cursor:pointer}
section{background:#fff;margin:14px 0;padding:16px;border-left:5px solid #C4C4CD;overflow-wrap:anywhere}
section.ok{border-color:#2DB757}section.corriger{border-color:#FF9831}section.rejeter{border-color:#E0301E}
header{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px}header span{background:#EEEEF3;padding:1px 8px}
small,.origine,.consigne{color:#747480;font-size:13px}h2{font-size:18px;margin:2px 0}.consigne{margin:0 0 8px}
details{background:#F6F6FA;padding:8px;margin:8px 0}summary{cursor:pointer}
table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{text-align:left;vertical-align:top;padding:7px;border-top:1px solid #E3E3EA}
th{font-size:13px;color:#747480}td+td{color:#555563;font-size:13.5px}.src{background:#FFE600;padding:0 5px}em{color:#A35200;font-size:12px}
.doute{background:#FFF3D6;padding:6px 8px;margin:8px 0;font-size:13.5px}.ass{background:#FBE3E0;padding:1px 6px;font-size:12px}
.choix{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;align-items:center}.choix input[type=text]{flex:1;min-width:180px;padding:6px;font:inherit}
#sortie{width:100%;height:140px}"""

_JS = """const S=[...document.querySelectorAll('section')],K='cadrage-pilote-v3';let D={};
try{D=JSON.parse(localStorage.getItem(K))||{}}catch(e){}
function maj(){let n=0;for(const s of S){const d=D[s.dataset.id]||{};s.className=d.v||'';if(d.v)n++}
 document.getElementById('compte').textContent=n+' / '+S.length+' relus';
 document.getElementById('sortie').value='Validation pilote v3 ('+n+'/'+S.length+')\\n'+S.map(s=>{const d=D[s.dataset.id]||{};
  return s.dataset.n+' '+s.dataset.id+' : '+(d.v||'non relu')+(d.r?' - '+d.r:'')}).join('\\n');
 try{localStorage.setItem(K,JSON.stringify(D))}catch(e){}}
for(const s of S){const id=s.dataset.id,t=s.querySelector('input[type=text]');
 for(const r of s.querySelectorAll('input[type=radio]')){r.checked=(D[id]||{}).v===r.value;r.onchange=()=>{(D[id]=D[id]||{}).v=r.value;maj()}}
 t.value=(D[id]||{}).r||'';t.oninput=()=>{(D[id]=D[id]||{}).r=t.value;maj()}}
document.getElementById('copier').onclick=async e=>{const o=document.getElementById('sortie');
 try{await navigator.clipboard.writeText(o.value);e.target.textContent='Copié : colle-le à Claude'}
 catch(x){o.scrollIntoView();o.select();e.target.textContent='Fais Ctrl+C, puis colle-le à Claude'}};
maj();"""


def render_html(examples: list[dict]) -> str:
    E, cards, n_all = html.escape, [], len(examples)
    for n, ex in enumerate(examples, 1):
        r, m = ex["review"], ex["meta"]
        rows = "".join(
            f'<tr><td>{E(p["text"])} <b class="src">{p["label"]}</b>'
            + (f' <em>{E(p["theme"])} · gravité {p["gravite"]} (écrits par l’assistant)</em>' if "theme" in p else "")
            + (f' <span class="ass">{E(p["origine"])}</span>' if p["origine"] != "recopiée" else "")
            + f'</td><td>{E(r["passages"][[a for a, _ in r["passages"]].index(p["label"])][1][:700])}</td></tr>'
            for p in r["phrases"])
        ps = "".join(f"<p><b>{lab}</b> {E(t)}</p>" for lab, t in r["passages"])
        radios = "".join(f'<label><input type="radio" name="{r["id"]}" value="{v}"> {lab}</label>'
                         for v, lab in (("ok", "Bon"), ("corriger", "À corriger"), ("rejeter", "Rejeter")))
        doute = f'<p class="doute"><b>Mon doute :</b> {E(r["doute"])}</p>' if r["doute"] else ""
        by = ("consigne écrite par l’assistant" if m["consigne_ecrite_par"] == "assistant"
              else "consigne : " + E(m["consigne_ecrite_par"]))
        cards.append(f"""<section data-id="{r['id']}" data-n="{n}">
<header><b>{n}/{n_all}</b><span>{E(r['type'])}</span><span>{m['split']}</span><span>{E(m['source'])}</span></header>
<small>Entrée : la demande</small><h2>{E(r['titre'])}</h2><p class="consigne">{E(r['consigne'])}</p>
<details><summary>Entrée : les {len(r['passages'])} passage(s) fournis au modèle</summary>{ps}</details>
<table><tr><th>Sortie attendue</th><th>Preuve dans l’entrée (passage cité)</th></tr>{rows}</table>{doute}
<div class="origine">Source : {E(r['src']['titre'])} · {E(r['src']['editeur'])} · {E(r['src']['licence'])} ·
<a href="{E(r['src']['url'])}">document</a> · {by} · {E(m['sortie_ecrite_par'])}</div>
<div class="choix">{radios}<input type="text" placeholder="Remarque"></div></section>""")
    intro = ("<p>Pour chaque exemple : <b>la sortie répond-elle à la demande, et chaque phrase est-elle prouvée par la colonne de droite ?</b> "
             "Les textes sont des documents publics (Cour des comptes européenne, CC BY 4.0 ; Licence Ouverte 2.0 pour les pièces de marché). "
             "Les phrases sont recopiées ; les mentions « assemblée » joignent une amorce et un alinéa ; thèmes, gravités et consignes marquées "
             "« assistant » sont écrits par Claude. Aucun humain n’a encore validé ces exemples.</p>")
    return (f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Validation des {n_all} exemples (v3)</title><style>{_CSS}</style></head><body><div class="top"><strong>Cadrage</strong>'
            f'<span>Validation du jeu d’entraînement v3 : {n_all} exemples</span><span id="compte"></span>'
            f'<button id="copier">Copier mes décisions</button></div><main>{intro}' + "\n".join(cards) +
            f'<textarea id="sortie" readonly placeholder="Tes décisions à coller dans la conversation"></textarea></main><script>{_JS}</script></body></html>')


def write_outputs(examples: list[dict], out_dir: Path, hashes: dict[str, str] | None = None) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(examples)

    def dump(name: str, items: list[dict]) -> None:
        with (out_dir / name).open("w", encoding="utf-8", newline="\n") as f:
            for e in items:
                f.write(json.dumps({"messages": e["messages"], "meta": e["meta"]}, ensure_ascii=False) + "\n")

    dump(f"pilote-{n}.jsonl", examples)
    dump(f"pilote-{n}-train.jsonl", [e for e in examples if e["meta"]["split"] == "train"])
    dump(f"pilote-{n}-test.jsonl", [e for e in examples if e["meta"]["split"] == "test"])
    stats = statistics_of(examples, hashes)
    (out_dir / f"pilote-{n}-stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / f"validation-{n}-exemples.html").write_text(render_html(examples), encoding="utf-8")
    return stats


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    texts = {sid: source_text(a.sources_dir, sid) for sid in SOURCES}
    hashes = {sid: hashlib.sha256((a.sources_dir / f"{sid}.pdf").read_bytes()).hexdigest()
              for sid in SOURCES if (a.sources_dir / f"{sid}.pdf").exists()}
    examples = build_all(texts)
    print(json.dumps(write_outputs(examples, a.out_dir, hashes), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
