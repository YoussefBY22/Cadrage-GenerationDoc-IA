"""API HTTP : découverte automatique des routeurs `routes_*.py`."""

import importlib
import pkgutil

from fastapi import APIRouter


def discover_routers() -> list[APIRouter]:
    """Importe chaque module `routes_*` (ordre alphabétique) et renvoie leur `router`."""
    routers: list[APIRouter] = []
    names = sorted(m.name for m in pkgutil.iter_modules(__path__) if m.name.startswith("routes_"))
    for name in names:
        module = importlib.import_module(f"{__name__}.{name}")
        router = getattr(module, "router", None)
        if router is not None:
            routers.append(router)
    return routers
