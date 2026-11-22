"""Génère le projet Power BI (PBIP) : modèle TMDL, rapport PBIR, `bi/measures.dax` et `bi/KPI.md`.

Usage : python bi/pbip/build_pbip.py [--csv DOSSIER]   (idempotent)

- indicateurs.py : définitions, formules DAX et seuils (source unique)
- modele.py      : tables en français, Power Query, relations
- rapport.py     : pages, barre latérale, visuels (briques dans pbir.py)
- ../theme/cadrage-ey.json : thème copié dans les ressources du rapport

Ne pas enregistrer depuis Power BI Desktop : la génération suivante écraserait ses modifications.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from indicateurs import kpi_md, measures_dax
from modele import construire_modele, ecrire
from rapport import construire_rapport

RACINE = Path(__file__).resolve().parent
BI = RACINE.parent
CSV_PAR_DEFAUT = r"C:\Users\youss\Desktop\PFE-IA-Cadrage\bi\export"


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère le projet Power BI")
    parser.add_argument("--csv", default=CSV_PAR_DEFAUT, help="chemin absolu du dossier des CSV (DossierCsv)")
    args = parser.parse_args()

    modele, rapport = RACINE / "CadrageIA.SemanticModel", RACINE / "CadrageIA.Report"
    # Seules les parties générées sont effacées ; le cache local `.pbi/` de Power BI est laissé en place.
    for dossier in (modele / "definition", rapport / "definition",
                    rapport / "StaticResources" / "RegisteredResources"):
        if dossier.exists():
            shutil.rmtree(dossier)

    construire_modele(modele, args.csv)
    construire_rapport(rapport, BI / "theme" / "cadrage-ey.json")
    ecrire(BI / "measures.dax", measures_dax())
    ecrire(BI / "KPI.md", kpi_md())
    ecrire(RACINE / "CadrageIA.pbip", json.dumps(
        {"version": "1.0", "artifacts": [{"report": {"path": "CadrageIA.Report"}}],
         "settings": {"enableAutoRecovery": True}}, indent=2) + "\n")
    print("PBIP généré dans", RACINE)


if __name__ == "__main__":
    main()
