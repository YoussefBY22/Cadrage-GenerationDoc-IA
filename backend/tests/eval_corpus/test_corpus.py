"""Tests du corpus synthétique or (lot B4) : déterminisme, unicité des marqueurs, pièges, gold."""

import hashlib
import json
import re
import time
from pathlib import Path

import pytest
from docx import Document
from pptx import Presentation
from pypdf import PdfReader

from eval.corpus.generate import Gold, generate

SEED = 7


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace(" ", " ")).strip()


def read_text(path: Path) -> str:
    """Extrait le texte d'un fichier du corpus, directement avec les bibliothèques de format."""
    ext = path.suffix
    if ext == ".txt":
        return path.read_text(encoding="utf-8")
    if ext == ".docx":
        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs]
        for t in doc.tables:
            parts += [c.text for row in t.rows for c in row.cells]
        return "\n".join(parts)
    if ext == ".pdf":
        return "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
    if ext == ".pptx":
        out = []
        for slide in Presentation(str(path)).slides:
            for sh in slide.shapes:
                if sh.has_text_frame:
                    out.append(sh.text_frame.text)
        return "\n".join(out)
    raise ValueError(ext)


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("corpus")
    t0 = time.perf_counter()
    gold = generate(SEED, out)
    return out, gold, time.perf_counter() - t0


def test_generation_rapide(corpus):
    assert corpus[2] < 20


def test_gold_valide_et_tailles(corpus):
    out, gold, _ = corpus
    reloaded = Gold.model_validate(json.loads((out / "gold.json").read_text(encoding="utf-8")))
    assert reloaded == gold
    assert len(gold.facts) == 60
    assert all(sum(f.institution == i for f in gold.facts) == 20 for i in ("VAL", "ARV", "LOR"))
    assert len(gold.queries) == 30
    assert len(gold.traps) == 5
    assert len(gold.no_evidence) == 10
    assert all(8 <= sum(f.institution == i for f in gold.findings) <= 12
               for i in ("VAL", "ARV", "LOR"))
    assert gold.dependencies


def test_meme_graine_memes_empreintes(corpus, tmp_path):
    out, gold, _ = corpus
    gold2 = generate(SEED, tmp_path)
    assert gold2 == gold
    assert (tmp_path / "gold.json").read_bytes() == (out / "gold.json").read_bytes()
    for txt in sorted(out.rglob("*.txt")):
        other = tmp_path / txt.relative_to(out)
        assert hashlib.sha256(txt.read_bytes()).hexdigest() == \
            hashlib.sha256(other.read_bytes()).hexdigest()


def test_autre_graine_change_les_valeurs(corpus, tmp_path):
    _, gold, _ = corpus
    assert generate(SEED + 1, tmp_path).facts != gold.facts


def test_formats_presents_et_diagnostic_8_a_12_pages(corpus):
    out = corpus[0]
    for inst in ("VAL", "ARV", "LOR"):
        for name in ("diagnostic.txt", "diagnostic.docx", "diagnostic.pdf", "priorites.docx",
                     "atelier.pptx"):
            assert (out / inst / name).is_file()
        pages = len(PdfReader(str(out / inst / "diagnostic.pdf")).pages)
        assert 8 <= pages <= 12


def test_chaque_marqueur_dans_exactement_un_document(corpus):
    out, gold, _ = corpus
    texts = {}  # id logique -> texte normalisé par format
    for doc in gold.documents:
        texts[doc.id] = {fmt: _norm(read_text(out / p)) for fmt, p in doc.paths.items()}
    for trap in gold.traps:
        texts[trap.id] = {"x": _norm(read_text(out / trap.path))}
    markers = [f.marker for f in gold.facts]
    assert len(set(markers)) == len(markers)
    for fact in gold.facts:
        holders = [d for d, by_fmt in texts.items()
                   if any(_norm(fact.marker) in t for t in by_fmt.values())]
        assert holders == [fact.document], fact.marker
        # mêmes contenus dans les trois formats du diagnostic
        assert all(_norm(fact.marker) in t for t in texts[fact.document].values())
    for q in gold.queries:
        assert all(m in markers for m in q.expected_markers)
    for f in gold.findings:
        assert all(m in markers for m in f.evidence_markers)


def test_dependances_dans_la_note_de_priorites(corpus):
    out, gold, _ = corpus
    for dep in gold.dependencies:
        text = _norm(read_text(out / dep.institution / "priorites.docx"))
        assert dep.marker in text


def test_chaque_piege_contient_le_canari(corpus):
    out, gold, _ = corpus
    for trap in gold.traps:
        path = out / trap.path
        assert trap.canary == "ZX-CANARI-7"
        assert "ZX-CANARI-7" in read_text(path), trap.id
    kinds = {t.kind for t in gold.traps}
    assert {"injection_fr", "injection_en", "faux_delimiteurs", "texte_cache",
            "chiffre_contradictoire"} <= kinds
    contra = next(t for t in gold.traps if t.kind == "chiffre_contradictoire")
    fact = next(f for f in gold.facts if f.id == contra.contradicts_fact)
    assert contra.contradiction_marker != fact.marker
    assert contra.contradiction_marker in _norm(read_text(out / contra.path))


def test_sujets_sans_preuve_absents_du_corpus(corpus):
    out, gold, _ = corpus
    files = [p for p in out.rglob("*") if p.suffix in {".txt", ".docx", ".pdf", ".pptx"}]
    alltext = "\n".join(read_text(p) for p in files).lower()
    for ne in gold.no_evidence:
        assert ne.forbidden_keyword.lower() not in alltext, ne.id
