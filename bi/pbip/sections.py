"""Libellé lisible et rôle de chaque section, lus dans les gabarits de l'application.

Clé « type|code » (ex. « cdc|chg_parties ») : c'est la clé que porte chaque génération dans l'entrepôt.
Le rôle est la première phrase de la consigne du gabarit, mise à la troisième personne quand elle commence
par un impératif (« Décris les parties prenantes » → « Décrit les parties prenantes »). Aucune clé technique ne s'affiche.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

GABARITS = Path(__file__).resolve().parents[2] / "backend" / "app" / "generation" / "templates"
LIVRABLES = {"tor": "TdR", "cdc": "CdC", "roadmap": "Feuille de route", "findings": "Constats"}
ETAPES = [  # appels au modèle qui ne sont pas des sections de livrable
    ("findings|_findings", "Extraction des constats", "Lit les rapports d'audit et en extrait les constats, un par entrée.",
     "Constats"),
    ("roadmap|_axes", "Regroupement en axes", "Nomme les axes de transformation qui regroupent les constats.",
     "Feuille de route"),
    ("roadmap|_initiatives", "Initiatives par axe", "Propose les initiatives de chaque axe, rattachées à leurs constats.",
     "Feuille de route"),
]


def _role(consigne: str) -> str:
    phrase = re.split(r"(?<=[.!?])\s", " ".join(consigne.split()), maxsplit=1)[0]
    phrase = phrase.replace(", d'après les sources", "").replace(", d'après les passages", "")
    for imperatif, present in (("Décris", "Décrit"), ("Extrais", "Extrait")):
        if phrase.startswith(imperatif + " "):
            phrase = present + phrase[len(imperatif):]
    if len(phrase) > 160:
        phrase = phrase[:159].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return phrase


def sections() -> list[tuple[str, str, str, str]]:
    out: dict[str, tuple[str, str, str, str]] = {}
    for f in sorted((GABARITS / "fr").glob("*.yaml")):
        g = yaml.safe_load(f.read_text(encoding="utf-8"))
        for s in g.get("sections", []):
            cle = f"{g['type']}|{s['key']}"
            out[cle] = (cle, s["title"], _role(s.get("instructions", "")), LIVRABLES.get(g["type"], g["type"]))
    for f in sorted((GABARITS / "modules").glob("*.yaml")):
        g = yaml.safe_load(f.read_text(encoding="utf-8"))["fr"]
        for typ in ("tor", "cdc"):
            for s in (g.get(typ) or {}).get("sections", []):
                cle = f"{typ}|{s['key']}"
                titre = f"{s['title']} ({g['label'][0].lower()}{g['label'][1:]})"
                out.setdefault(cle, (cle, titre, _role(s.get("instructions", "")), LIVRABLES[typ]))
    for e in ETAPES:
        out[e[0]] = e
    # Libellé court et unique : le titre du gabarit ; en cas d'homonymie, le livrable entre parenthèses.
    lignes = sorted(out.values())
    vus: dict[str, int] = {}
    for _, titre, _, _ in lignes:
        court = titre.split(" (")[0]
        vus[court] = vus.get(court, 0) + 1
    return [(cle, titre.split(" (")[0] + (f" ({livrable})" if vus[titre.split(" (")[0]] > 1 else ""),
             role if "(" not in titre else f"{role} Module : {titre.split(' (', 1)[1].rstrip(')')}.", livrable)
            for cle, titre, role, livrable in lignes]


if __name__ == "__main__":
    for s in sections():
        print(" | ".join(s))
