"""Génère le projet Power BI (PBIP) : modèle TMDL, rapport PBIR, `bi/measures.dax` et `bi/KPI.md`.

Usage : python bi/pbip/build_pbip.py [--csv DOSSIER]   (idempotent)

- indicateurs.py : définitions, formules DAX et seuils (source unique)
- modele.py      : tables en français, Power Query, relations
- rapport.py     : pages, barre latérale, visuels (briques dans pbir.py)
- sections.py    : libellé et rôle de chaque section, lus dans les gabarits
- ../theme/cadrage.json : thème copié dans les ressources du rapport

Ne pas enregistrer depuis Power BI Desktop : la génération suivante écraserait ses modifications.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
from pathlib import Path

from indicateurs import kpi_md, measures_dax
from modele import construire_modele, ecrire
from rapport import PROJET_PAR_DEFAUT, TOUS, construire_rapport, pages

RACINE = Path(__file__).resolve().parent
BI = RACINE.parent
CSV_PAR_DEFAUT = r"C:\Users\youss\Desktop\PFE-IA-Cadrage\bi\export"


def projet_reel(dossier: Path) -> str | None:
    """Projet ouvert par défaut sur la page Projet : le premier projet réel de l'export, s'il existe."""
    fichier = dossier / "v_project.csv"
    if not fichier.exists():
        return None
    with open(fichier, encoding="utf-8-sig", newline="") as f:
        texte = f.read()
    lignes = list(csv.DictReader(texte.splitlines(), delimiter=";" if texte.count(";") > texte.count(",") else ","))
    reels = sorted(r["mission_name"] for r in lignes if r.get("is_demo") in ("false", "0", ""))
    return reels[0] if reels else None


def effacer(dossier: Path) -> None:
    """Windows garde parfois un fichier verrouillé quelques secondes après la fermeture de Power BI."""
    for essai in range(6):
        if not dossier.exists():
            return
        try:
            shutil.rmtree(dossier)
            return
        except PermissionError:
            if essai == 5:
                raise
            time.sleep(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère le projet Power BI")
    parser.add_argument("--csv", default=CSV_PAR_DEFAUT, help="chemin absolu du dossier des CSV (DossierCsv)")
    args = parser.parse_args()

    modele, rapport = RACINE / "CadrageIA.SemanticModel", RACINE / "CadrageIA.Report"
    # Seules les parties générées sont effacées ; le cache local `.pbi/` de Power BI est laissé en place.
    for dossier in (modele / "definition", rapport / "definition",
                    rapport / "StaticResources" / "RegisteredResources"):
        effacer(dossier)

    PROJET_PAR_DEFAUT["valeur"] = projet_reel(Path(args.csv)) or TOUS
    liste = pages()  # d'abord : les pages déclarent les sous-titres que le modèle porte en mesures
    construire_modele(modele, args.csv)
    construire_rapport(rapport, BI / "theme" / "cadrage.json", liste)
    ecrire(BI / "measures.dax", measures_dax())
    ecrire(BI / "KPI.md", kpi_md())
    ecrire(RACINE / "CadrageIA.pbip", json.dumps(
        {"version": "1.0", "artifacts": [{"report": {"path": "CadrageIA.Report"}}],
         "settings": {"enableAutoRecovery": True}}, indent=2) + "\n")
    print("PBIP généré dans", RACINE)


if __name__ == "__main__":
    main()
