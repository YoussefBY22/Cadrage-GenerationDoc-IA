"""Recherche : requêtes et passages remis au modèle."""

from pydantic import BaseModel, ConfigDict

from .documents import Chunk


class Passage(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str  # "P1".."Pn" : seule référence vue par le modèle
    chunk: Chunk
    score: float
    ranks: dict[str, int]  # {"bm25": 3, "vector": 7}


class SearchQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    dossier_id: str
    texts: list[str]
    k: int = 10
    document_ids: list[str] | None = None
    lexical_only: bool = False  # mots exacts seulement (BM25) : instantané, sans appel au modèle de vecteurs
