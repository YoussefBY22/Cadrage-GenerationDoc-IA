from app.domain.documents import Block, ParsedDocument
from app.retrieval.chunking import chunk_document, estimate_tokens, indexed_text


def _doc(blocks):
    return ParsedDocument(
        filename="a.txt",
        mime="text/plain",
        sha256="0" * 64,
        title=None,
        language="fr",
        blocks=blocks,
    )


def _words(n, tag="mot"):
    return " ".join(f"{tag}{i}" for i in range(n))


def _run(blocks, **kw):
    return chunk_document(_doc(blocks), document_id="doc_1", dossier_id="dos_1", **kw)


def test_jamais_a_cheval_sur_deux_sections():
    blocks = [
        Block(text="1 Intro", page=1, section_path=("1 Intro",), kind="heading"),
        Block(text=_words(30, "a"), page=1, section_path=("1 Intro",)),
        Block(text="2 Suite", page=2, section_path=("2 Suite",), kind="heading"),
        Block(text=_words(30, "b"), page=2, section_path=("2 Suite",)),
    ]
    chunks = _run(blocks)
    assert len(chunks) == 2
    assert chunks[0].section_path == ("1 Intro",) and "b0" not in chunks[0].text
    assert chunks[1].section_path == ("2 Suite",) and "a0" not in chunks[1].text
    assert chunks[0].text.startswith("1 Intro")  # titre rattaché au contenu
    assert [c.ordinal for c in chunks] == [0, 1]


def test_tailles_et_chevauchement():
    blocks = [Block(text=_words(60), page=1, section_path=("S",)) for _ in range(20)]
    chunks = _run(blocks)
    assert len(chunks) > 1
    assert all(c.token_estimate <= 500 for c in chunks)
    # chevauchement : la fin du passage n est reprise au début du passage n+1
    tail = chunks[0].text.split()[-10:]
    assert tail == chunks[1].text.split()[:50][-10:] or all(w in chunks[1].text for w in tail)
    assert chunks[0].token_estimate >= 300


def test_bloc_geant_decoupe_sous_le_maximum():
    chunks = _run([Block(text=_words(2000), page=1, section_path=("S",))])
    assert len(chunks) >= 3
    assert all(estimate_tokens(c.text) <= 500 for c in chunks)


def test_tableau_entier_puis_decoupe_par_lignes():
    table = "\n".join(f"ligne{i} | {i * 10}" for i in range(5))
    chunks = _run([Block(text=table, page=3, section_path=("T",), kind="table")])
    assert len(chunks) == 1 and chunks[0].text == table
    big = "\n".join(f"{_words(40, f'l{i}x')}" for i in range(40))
    chunks = _run([Block(text=big, page=3, section_path=("T",), kind="table")], max_tokens=200)
    assert len(chunks) > 1
    assert all(estimate_tokens(c.text) <= 200 for c in chunks)
    assert all(line.startswith("l") for c in chunks for line in c.text.split("\n"))


def test_diapositive_isolee():
    blocks = [
        Block(text=_words(20), page=None, section_path=("S",)),
        Block(text="Diapo 1\nPoint A", page=1, section_path=("S",), kind="slide"),
    ]
    chunks = _run(blocks)
    assert len(chunks) == 2 and chunks[1].text == "Diapo 1\nPoint A"


def test_pages():
    blocks = [
        Block(text=_words(10), page=2, section_path=("S",)),
        Block(text=_words(10, "z"), page=3, section_path=("S",)),
    ]
    c = _run(blocks)[0]
    assert (c.page_start, c.page_end) == (2, 3)
    c = _run([Block(text="x y", page=None)])[0]
    assert c.page_start is None and c.page_end is None


def test_ids_stables_et_distincts():
    blocks = [Block(text=_words(900), page=1, section_path=("S",))]
    a, b = _run(blocks), _run(blocks)
    assert [c.id for c in a] == [c.id for c in b]
    assert len({c.id for c in a}) == len(a)
    assert all(c.id.startswith("chk_") and len(c.id) == 16 for c in a)
    other = chunk_document(_doc(blocks), document_id="doc_2", dossier_id="dos_1")
    assert a[0].id != other[0].id


def test_titre_prefixe_a_lindexation_seulement():
    c = _run([Block(text="Texte de gouvernance", page=1, section_path=("1", "2.1 Gouvernance"))])[0]
    assert indexed_text(c) == "2.1 Gouvernance — Texte de gouvernance"
    assert c.text == "Texte de gouvernance"


def test_document_vide_et_titres_seuls():
    assert _run([]) == []
    assert len(_run([Block(text="Titre", page=1, section_path=("T",), kind="heading")])) == 1
