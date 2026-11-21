"""Scripts d'entraînement LoRA ; ajoute backend/ au chemin d'import (app, eval) pour les commandes."""

import sys
from pathlib import Path

_BACKEND = str(Path(__file__).resolve().parents[1] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
