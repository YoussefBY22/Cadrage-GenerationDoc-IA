"""Rappel@10 de la recherche sur le corpus or B4 (FakeProvider), via le vrai service d'ingestion."""

import re
from pathlib import Path

from app.config import Settings
from app.domain.workflow import CurrentUser
from app.services import ingestion
from app.services.search import SearchService
from eval.corpus.generate import generate

SEED = 7
K = 10
THRESHOLD = 0.90
USER = CurrentUser(id="usr_dev", role="admin")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace(" ", " ").replace(" ", " ")).strip().lower()


def test_rappel_at_10_corpus_or(repo, provider, tmp_path):
    gold = generate(SEED, tmp_path / "corpus")
    settings = Settings(upload_dir=str(tmp_path / "up"), max_upload_mb=25)
    search = SearchService(repo, provider)
    dossiers: dict[str, str] = {}
    for doc in gold.documents:  # une institution = un dossier ; tous les formats sont importés
        did = dossiers.setdefault(
            doc.institution, repo.create_dossier(doc.institution, doc.institution, "fr", "usr_dev"))
        for rel in doc.paths.values():
            path = Path(tmp_path / "corpus" / rel)
            try:
                ingestion.ingest(repo, provider, did, path.name, path.read_bytes(), USER,
                                 search=search, settings=settings)
            except ingestion.IngestionError as exc:  # TXT/DOCX/PDF identiques ne sont pas des doublons
                assert exc.status != 409, rel
                raise

    hits = 0
    misses: list[str] = []
    for q in gold.queries:
        passages = search.search(dossiers[q.institution], [q.text], K)
        text = _norm(" ".join(p.chunk.text for p in passages))
        if all(_norm(m) in text for m in q.expected_markers):
            hits += 1
        else:
            misses.append(q.id)
    recall = hits / len(gold.queries)
    print(f"rappel@{K} = {recall:.3f} ({hits}/{len(gold.queries)}) ; manqués : {misses}")
    assert recall >= THRESHOLD, misses
