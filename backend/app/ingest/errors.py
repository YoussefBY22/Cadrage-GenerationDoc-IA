"""Erreurs de lecture de documents."""


class IngestError(Exception):
    """Base des erreurs d'ingestion."""


class UnsupportedFormat(IngestError):
    """Extension ou signature non prise en charge."""


class ParseError(IngestError):
    """Fichier corrompu ou illisible."""
