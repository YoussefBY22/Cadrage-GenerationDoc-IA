"""Jeu d'entraînement à partir du corpus public réel (lot T4, 08 §7.1).

Entrées : `data/public/manifest.json` + `data/public/raw/` (voir `data/public/fetch.py`). Aucun réseau, aucun LLM :
les réponses sont **extractives** (la phrase du passage, citée avec son étiquette), donc le vérificateur
(`filter.py`) les valide par construction ; les refus et les pièges suivent les proportions de 08 §7.1.

Séparation **par groupe de documents** : un groupe = une paire diagnostic → livrable (et ses traductions FR/EN
pour l'UE). Quatre parties disjointes : train / val / test et `gold` (réservé à l'évaluation réelle, jamais
utilisé pour l'entraînement). Usage :
    python -m training.dataset.real --out-dir training/data/real --seed 7
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from app.generation import prompting
from app.generation.template_loader import SectionSpec
from training.dataset import build as synth
from training.dataset.extract import (
    WORDS_PER_PAGE,
    ROOT,
    chunk_paragraphs,
    load_manifest,
    read_document,
    sentences,
)
from training.dataset.filter import filter_examples
from training.dataset.split import split_by_source

LICENCE_NOTE = "voir data/LICENCES.md"
PER_DOC = 36  # exemples candidats maximum par document
GOLD_SHARE = 0.12
_STOP = {
    "en": set("the of and to in a for is on that by with as are be this from at or an it its was has have "
              "which their these been more also not will can such than other into between over under".split()),
    "fr": set("le la les de des du un une et en à au aux pour par sur dans que qui est sont ce cette ces "
              "avec ou se sa son ses leur leurs plus pas ne il elle ont été comme entre aussi dont".split()),
}
_NUM = re.compile(r"\d")
_FACT_OK = re.compile(r"^[A-ZÀ-ÝÉÈ“\"(].{40,320}[.]$")
OUT_DIR = ROOT / "training" / "data" / "real"


def group_of(entry: dict, by_pair: dict[str, list[dict]]) -> str:
    """Les traductions FR/EN d'un même dossier UE vont dans le même groupe (pas de fuite de traduction)."""
    if entry["source"] == "cellar":
        livrable = next(e for e in by_pair[entry["pair"]] if e["role"] == "livrable")
        return "eu-" + livrable["id"].split("-")[1]
    return entry["pair"]


def assign_groups(groups: list[str], seed: int) -> dict[str, str]:
    """group → train|val|test|gold. `gold` est tiré d'abord ; les autres suivent split_by_source (80/10/10)."""
    g = sorted(set(groups))
    random.Random(f"gold-{seed}").shuffle(g)
    n_gold = max(1, round(len(g) * GOLD_SHARE)) if len(g) >= 4 else 0
    mapping = {x: "gold" for x in g[:n_gold]}
    rest = [{"meta": {"source": x}} for x in g[n_gold:]]
    parts = split_by_source(rest, seed)
    for name, items in parts.items():
        for e in items:
            mapping[e["meta"]["source"]] = name
    return mapping


def keywords(text: str, lang: str, df: Counter, n_docs: int, k: int = 3) -> list[str]:
    toks = [t for t in re.findall(r"[A-Za-zÀ-ÿ]{5,}", text.lower()) if t not in _STOP[lang]]
    tf = Counter(toks)
    score = {t: c * math.log((1 + n_docs) / (1 + df[t])) for t, c in tf.items()}
    return [t for t, _ in sorted(score.items(), key=lambda x: (-x[1], x[0]))[:k]]


def fact_sentence(chunk: str) -> str | None:
    """Première phrase factuelle : un nombre, de 9 à 45 mots, sans URL ni élément de liste."""
    for s in sentences(chunk):
        w = len(s.split())
        if 9 <= w <= 45 and _NUM.search(s) and _FACT_OK.match(s) and "http" not in s and "|" not in s:
            return s
    return None


def _spec(title: str) -> SectionSpec:
    return SectionSpec(key=re.sub(r"\W+", "_", title.lower()), title=title,
                       instructions=f"Résume les constats chiffrés de la section « {title} ».",
                       queries=[title, f"{title} chiffres"], max_sentences=4)


def build_for_document(entry: dict, group: str, chunks: list[str], others: list[str], rng: random.Random,
                       df: Counter, n_docs: int) -> list[dict]:
    """Exemples candidats d'un document ; `others` = chunks d'autres documents (même langue) pour les refus."""
    lang = entry["lang"]
    cand = [(i, c, fact_sentence(c)) for i, c in enumerate(chunks)]
    cand = [x for x in cand if x[2]]
    rng.shuffle(cand)
    out = []
    for i, chunk, fact in cand[:PER_DOC]:
        kws = keywords(chunk, lang, df, n_docs)
        if not kws:
            continue
        title = " ".join(kws)
        kind = synth._pick_kind(rng)
        nonce = rng.randbytes(6).hex()
        inst = f"{entry['id']}"
        if kind == "refus":
            pool = [o for o in others if not any(k in o.lower() for k in kws)]
            if len(pool) < 3:
                kind = "section"
            else:
                texts = rng.sample(pool, 3)
                ch = [synth._chunk(group, inst, j, t, title) for j, t in enumerate(texts)]
                passages = synth._passages(ch)
                out.append(_ex(entry, group, kind, title, passages, synth._section_json(False),
                               prompting.build_section_prompt(_spec(title), passages, nonce=nonce)))
                continue
        distract = [c for j, c, _ in [(j, c, None) for j, c in enumerate(chunks)] if j != i and fact not in c]
        texts = [chunk, *rng.sample(distract, min(2, len(distract)))]
        if kind == "piege":
            texts[-1] = f"{texts[-1]} {synth.INJECTION}" if len(texts) > 1 else texts[-1]
            if len(texts) == 1:
                kind = "section"
        rng.shuffle(texts)
        ch = [synth._chunk(group, inst, j, t, title) for j, t in enumerate(texts)]
        passages = synth._passages(ch)
        label = next(p.label for p in passages if fact in p.chunk.text)
        if kind == "constats":
            user = prompting.build_findings_prompt(passages, nonce=nonce)
            answer = json.dumps({"status": "ok", "findings": [{
                "text": fact, "theme": title, "severity": "medium", "sources": [label]}]}, ensure_ascii=False)
        else:
            user = prompting.build_section_prompt(_spec(title), passages, nonce=nonce)
            answer = synth._section_json(True, fact, label)
        out.append(_ex(entry, group, kind, title, passages, answer, user))
    return out


def _ex(entry, group, kind, title, passages, answer, user) -> dict:
    ex = synth._example(group, entry["id"], kind, 0, user, answer, passages)
    ex["meta"].update({"licence": f"{entry['licence']} ({LICENCE_NOTE})", "document": entry["id"],
                       "lang": entry["lang"], "role": entry["role"], "pair": entry["pair"], "real": True})
    del ex["meta"]["seed"]
    ex["meta"]["seed"] = 0
    return ex


MIN_WORDS = 1000  # en dessous, le document est un résumé ou un extrait : écarté


def detect_lang(paras: list[str]) -> str:
    """Langue d'après les mots-outils (le champ `lang` des API est parfois faux : fichier anglais étiqueté français)."""
    toks = re.findall(r"[a-zà-ÿ]+", " ".join(paras).lower())
    fr = sum(t in _STOP["fr"] for t in toks)
    en = sum(t in _STOP["en"] for t in toks)
    return "fr" if fr > en else "en"


def load_corpus(raw_dir: Path | None = None) -> list[dict]:
    """Documents téléchargés avec leurs paragraphes nettoyés et leurs chunks."""
    docs = []
    for e in load_manifest():
        paras = read_document(e, raw_dir) if raw_dir else read_document(e)
        if not paras:
            continue
        words = sum(len(p.split()) for p in paras)
        if words < MIN_WORDS:
            continue
        e = {**e, "lang": detect_lang(paras)}
        chunks = chunk_paragraphs(paras)
        docs.append({"entry": e, "paras": paras, "chunks": chunks, "words": words,
                     "tokens": sum(prompting.estimate_tokens(p) for p in paras),
                     "pages": max(1, round(words / WORDS_PER_PAGE))})
    return docs


def build_all(docs: list[dict], seed: int = 7) -> tuple[list[dict], dict[str, str]]:
    by_pair = defaultdict(list)
    for d in docs:
        by_pair[d["entry"]["pair"]].append(d["entry"])
    groups = {d["entry"]["id"]: group_of(d["entry"], by_pair) for d in docs}
    assign = assign_groups(list(groups.values()), seed)
    df: Counter = Counter()
    for d in docs:
        df.update({t for t in re.findall(r"[A-Za-zÀ-ÿ]{5,}", " ".join(d["chunks"]).lower())})
    by_lang = defaultdict(list)
    for d in docs:
        by_lang[d["entry"]["lang"]].append(d)
    examples = []
    for d in docs:
        e = d["entry"]
        g = groups[e["id"]]
        if assign[g] == "gold":
            continue  # jamais d'exemple d'entraînement tiré d'un document du jeu or
        others = [c for o in by_lang[e["lang"]] if groups[o["entry"]["id"]] != g for c in o["chunks"][::7]]
        rng = random.Random(f"real-{seed}-{e['id']}")
        examples += build_for_document(e, g, d["chunks"], others, rng, df, len(docs))
    return examples, assign


def statistics(docs: list[dict], parts: dict[str, list[dict]], assign: dict[str, str], groups_by_doc: dict[str, str],
               rejects: dict[str, int]) -> dict:
    lang = Counter(d["entry"]["lang"] for d in docs)
    ex_lang = Counter(e["meta"]["lang"] for p in parts.values() for e in p)
    return {
        "documents": len(docs), "documents_par_langue": dict(lang),
        "documents_par_role": dict(Counter(d["entry"]["role"] for d in docs)),
        "documents_par_source": dict(Counter(d["entry"]["source"] for d in docs)),
        "pages_estimees": sum(d["pages"] for d in docs), "mots": sum(d["words"] for d in docs),
        "jetons_estimes": sum(d["tokens"] for d in docs),
        "exemples": {k: len(v) for k, v in parts.items()}, "exemples_par_langue": dict(ex_lang),
        "exemples_par_type": dict(Counter(e["meta"]["kind"] for p in parts.values() for e in p)),
        "groupes_par_partie": dict(Counter(assign.values())), "rejets_filtre": rejects,
        "documents_gold": sorted(d["entry"]["id"] for d in docs if assign[groups_by_doc[d["entry"]["id"]]] == "gold"),
    }


def run(out_dir: Path, seed: int = 7, raw_dir: Path | None = None) -> dict:
    docs = load_corpus(raw_dir)
    if not docs:
        raise SystemExit("aucun document dans data/public/raw/ : lancer `python data/public/fetch.py download`")
    cands, assign = build_all(docs, seed)
    kept, rejects = filter_examples(cands)
    parts = {"train": [], "val": [], "test": []}
    for e in kept:
        parts[assign[e["meta"]["source"]]].append(e)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, items in parts.items():
        (out_dir / f"{name}.jsonl").write_text(
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in items), encoding="utf-8")
    by_pair = defaultdict(list)
    for d in docs:
        by_pair[d["entry"]["pair"]].append(d["entry"])
    gbd = {d["entry"]["id"]: group_of(d["entry"], by_pair) for d in docs}
    stats = statistics(docs, parts, assign, gbd, rejects)
    (out_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out_dir / "groups.json").write_text(json.dumps(assign, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    print(json.dumps(run(args.out_dir, args.seed), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
