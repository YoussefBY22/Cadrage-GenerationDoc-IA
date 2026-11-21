"""Interface unique vers le modèle de langage.

Tout le reste du code ne parle qu'à `LLMProvider` : on peut changer de modèle (ou utiliser le
faux modèle des tests) sans toucher à la logique métier (NFR-04, NFR-05).
"""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Erreur du fournisseur de modèle (réseau local, réponse invalide, configuration)."""


class LLMProvider(ABC):
    """Trois capacités : générer du texte, générer du JSON conforme à un schéma, vectoriser."""

    #: identifiant consigné dans le journal d'audit et l'entrepôt (NFR-07)
    name: str

    @abstractmethod
    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.0,
                 seed: int | None = 0, max_tokens: int | None = None) -> str:
        """Texte libre. Température basse par défaut : stable, adapté aux citations."""

    @abstractmethod
    def generate_structured(self, prompt: str, schema: type[T], *, system: str | None = None,
                            temperature: float = 0.0, seed: int | None = 0) -> T:
        """Retourne une instance validée de `schema` ; lève LLMError si impossible."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Un vecteur par texte (même dimension pour tous)."""

    @property
    @abstractmethod
    def embedding_dimension(self) -> int: ...
