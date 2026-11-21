"""Configuration pytest de training/ : backend/ dans sys.path et réseau externe coupé."""

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from tests import netguard


@pytest.fixture(autouse=True)
def _no_outbound_network():
    """Appliqué à TOUS les tests d'entraînement : le réseau externe est coupé."""
    uninstall = netguard.install()
    yield
    uninstall()
