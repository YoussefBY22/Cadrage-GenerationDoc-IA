"""Hachage des mots de passe avec argon2 (jamais de mot de passe en clair en base)."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Renvoie l'empreinte argon2 (sel inclus) du mot de passe."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Vrai si le mot de passe correspond ; jamais d'exception pour un mauvais mot de passe."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
