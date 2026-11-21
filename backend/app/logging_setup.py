"""Journalisation JSON qui ne contient JAMAIS le contenu des prompts ou des documents.

Règle : on journalise des métadonnées (taille, empreinte courte, durée), pas le texte.
Un texte client dans un journal serait une fuite de confidentialité.
"""

import hashlib
import json
import logging
import sys
from datetime import UTC, datetime

# Champs qui ne doivent jamais apparaître dans un journal : ils sont remplacés par une empreinte.
SENSITIVE_FIELDS = {"prompt", "text", "content", "passage", "document", "response"}

_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


def fingerprint(value: str) -> dict:
    """Résumé non réversible d'un texte : longueur + 8 premiers caractères du SHA-256."""
    return {"len": len(value), "sha256_8": hashlib.sha256(value.encode()).hexdigest()[:8]}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD:
                continue
            payload[key] = fingerprint(value) if key in SENSITIVE_FIELDS and isinstance(
                value, str
            ) else value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
