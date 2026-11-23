"""Registre de modèles (lot C1) : lister, tester, activer, revenir en arrière — sans réentraînement.

Le moteur n'est interrogé qu'en LECTURE (`/api/tags`, `/api/show`, `/api/ps`) ; seul le test
automatique envoie de courtes générations au modèle candidat. Rien n'est jamais téléchargé.
"""

from .errors import RegistryError
from .service import RegistryService

__all__ = ["RegistryError", "RegistryService"]
