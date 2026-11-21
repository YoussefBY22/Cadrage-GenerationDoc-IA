"""Vérification phrase par phrase (module pur : ni stockage ni API)."""

from .numbers import NumberMention, extract_numbers
from .support import lexical_support
from .verifier import resolve_labels, verify_section

__all__ = ["NumberMention", "extract_numbers", "lexical_support", "resolve_labels", "verify_section"]
