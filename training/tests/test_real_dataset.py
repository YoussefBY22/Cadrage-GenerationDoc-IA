"""Tests du jeu réel (lot T4) : extraction, exemples extractifs vérifiés, séparation par groupe, licences.

Aucun réseau ni fichier téléchargé : textes minuscules fabriqués ici ; les contrôles sur le corpus réel
(manifeste, jeu or) ne s'exécutent que si les fichiers existent.
"""

import json
import random
from collections import Counter
from pathlib import Path

import pytest

from training.dataset import real
from training.dataset.extract import ROOT, chunk_paragraphs, clean_text, html_to_text, sentences
from training.dataset.filter import filter_examples

FACT = "In 2019 the national utility lost 32 percent of the water it produced because of leaking pipes."
FILL = "The committee reviewed the institutional arrangements and the long term planning of the sector today."


def _doc(i: int, lang: str = "en", role: str = "diagnostic", pair: str = "wb-pair-01") -> dict:
    paras = [f"{FILL} Topic{j} reservoir {FACT.replace('32', str(30 + j + i))}" for j in range(8)]
    chunks = chunk_paragraphs(paras, max_words=60)
    entry = {"id": f"d{i}", "source": "okr", "lang": lang, "role": role, "pair": pair,
             "licence": "CC BY 3.0 IGO", "format": "txt"}
    return {"entry": entry, "chunks": chunks}


def test_clean_text_drops_toc_pagenumbers_and_repeated_headers():
    header = "World Bank Group confidential header line for every page"
    body = "The sector needs reforms to improve the quality of services delivered to rural households."
    raw = "\n\n".join([header, body, "Contents ........ 12 ........ 14 ........ 15 and more words here", "12", header,
                       header, header, "Short."])
    out = clean_text(raw)
    assert out == [body]


def test_clean_text_joins_wrapped_lines_and_hyphenation():
    out = clean_text("The infrastruc-\nture network covers most of the\nterritory of the country today.")
    assert out == ["The infrastructure network covers most of the territory of the country today."]


def test_html_to_text_skips_tables_and_scripts():
    html = "<p>Premier paragraphe.</p><table><tr><td>cellule</td></tr></table><script>x()</script><p>Second.</p>"
    text = html_to_text(html)
    assert "cellule" not in text and "x()" not in text and "Premier" in text and "Second" in text


def test_sentences_and_chunks_respect_limits():
    p = " ".join(f"Phrase numéro {i} avec assez de mots pour compter ici." for i in range(40))
    chunks = chunk_paragraphs([p], max_words=60)
    assert len(chunks) > 3 and all(len(c.split()) <= 70 for c in chunks)
    assert len(sentences(p)) == 40


def test_fact_sentence_needs_a_number():
    assert real.fact_sentence(f"{FILL} {FACT}") == FACT
    assert real.fact_sentence(FILL) is None


def test_examples_are_extractive_and_pass_the_verifier():
    docs = [_doc(i) for i in range(4)]
    df = Counter()
    others = [c for d in docs[1:] for c in d["chunks"]]
    ex = real.build_for_document(docs[0]["entry"], "wb-pair-01", docs[0]["chunks"], others,
                                 random.Random(1), df, 4)
    assert len(ex) >= 5
    kept, rejects = filter_examples(ex)
    assert len(kept) == len(ex), rejects
    for e in kept:
        assert [m["role"] for m in e["messages"]] == ["system", "user", "assistant"]
        assert e["meta"]["real"] and "CC BY 3.0 IGO" in e["meta"]["licence"]
        assert "_verif" not in e
    assert "section" in {e["meta"]["kind"] for e in kept}


def test_split_is_by_group_with_disjoint_gold():
    groups = [f"g{i:02d}" for i in range(30)]
    a = real.assign_groups(groups, seed=7)
    assert set(a) == set(groups)
    assert {"train", "val", "test", "gold"} == set(a.values())
    assert a == real.assign_groups(list(reversed(groups)), seed=7)  # déterministe
    assert sum(v == "gold" for v in a.values()) >= 3


def test_translations_share_the_group_of_their_dossier():
    fr = {"id": "eu-52021SC0001-fr", "source": "cellar", "pair": "eu-pair-01", "role": "diagnostic"}
    fr2 = {"id": "eu-52021PC0002-fr", "source": "cellar", "pair": "eu-pair-01", "role": "livrable"}
    en = {"id": "eu-52021SC0001-en", "source": "cellar", "pair": "eu-pair-02", "role": "diagnostic"}
    en2 = {"id": "eu-52021PC0002-en", "source": "cellar", "pair": "eu-pair-02", "role": "livrable"}
    by_pair = {"eu-pair-01": [fr, fr2], "eu-pair-02": [en, en2]}
    assert {real.group_of(e, by_pair) for e in (fr, fr2, en, en2)} == {"eu-52021PC0002"}


def test_train_never_contains_gold_documents():
    docs = [_doc(i, pair=f"wb-pair-{i:02d}") for i in range(10)]
    for d in docs:
        d["words"], d["tokens"], d["pages"], d["paras"] = 100, 100, 1, []
    examples, assign = real.build_all(docs, seed=7)
    gold_groups = {g for g, part in assign.items() if part == "gold"}
    assert gold_groups
    assert not any(e["meta"]["source"] in gold_groups for e in examples)


# --- Contrôles sur le corpus réel (si téléchargé et construit) ---------------------------------
MANIFEST = ROOT / "data" / "public" / "manifest.json"


def test_manifest_licences_are_open_and_hashed():
    if not MANIFEST.exists():
        pytest.skip("manifeste absent")
    docs = json.loads(MANIFEST.read_text("utf-8"))["documents"]
    assert docs
    for d in docs:
        assert d["licence"].startswith(("CC BY 3.0 IGO", "CC BY 4.0", "Décision 2011/833/UE")), d["id"]
        assert "NC" not in d["licence"] and "ND" not in d["licence"]
        assert d["url"].startswith("https://") and d["licence_url"].startswith("http")
    assert all(len(d.get("sha256", "")) == 64 for d in docs if d.get("sha256"))
    assert sum(d.get("bytes", 0) for d in docs) <= 300 * 1024 * 1024


GOLD = ROOT / "backend" / "eval" / "corpus_public" / "gold_public.json"


def test_real_gold_is_disjoint_from_training_and_markers_exist():
    groups_file = ROOT / "training" / "data" / "real" / "groups.json"
    if not GOLD.exists() or not groups_file.exists():
        pytest.skip("jeu or ou découpage absents")
    gold = json.loads(GOLD.read_text("utf-8"))
    assert 20 <= len(gold["questions"]) <= 40
    assign = json.loads(groups_file.read_text("utf-8"))
    for q in gold["questions"]:
        assert assign[q["group"]] == "gold", q["id"]
        assert q["question"] and q["document"]
        assert q["marker"] if q["type"] == "fact" else q["absent_terms"]
    train_docs = {json.loads(line)["meta"]["document"]
                  for line in (groups_file.parent / "train.jsonl").read_text("utf-8").splitlines()}
    assert not ({q["document"] for q in gold["questions"]} & train_docs)


def test_gitignore_excludes_raw():
    assert "data/public/raw/" in (ROOT / ".gitignore").read_text("utf-8")
    assert Path(ROOT / "data" / "public" / "fetch.py").exists()
