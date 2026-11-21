import pytest

from . import netguard


@pytest.fixture(autouse=True)
def _no_outbound_network():
    """Appliqué à TOUS les tests : le réseau externe est coupé."""
    uninstall = netguard.install()
    yield
    uninstall()
