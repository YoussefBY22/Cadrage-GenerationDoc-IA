"""Identifiants et types élémentaires partagés."""

import uuid
from typing import Literal

Lang = Literal["fr", "en"]
DeliverableType = Literal["findings", "roadmap", "tor", "cdc"]

PREFIXES = ("dos", "doc", "chk", "fnd", "ini", "dlv", "run", "usr", "prt", "prj", "dec")


def new_id(prefix: str) -> str:
    """Renvoie « <prefix>_ » suivi de 12 caractères hexadécimaux aléatoires."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
