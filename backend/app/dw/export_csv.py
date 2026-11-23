"""Export CSV des vues (plan B de 07 §8 : Power BI → « Texte/CSV », sans base de données).

UTF-8 avec BOM (Excel et Power BI détectent l'encodage), séparateur « ; » et virgule décimale
(`--locale fr`, défaut) ou séparateur « , » et point décimal (`--locale en`).
"""

import argparse
import csv
from pathlib import Path

from sqlalchemy import Engine, text

from .schema import create_dw
from .views_sql import VIEWS, _prefix, create_views

LOCALES = {"fr": (";", ","), "en": (",", ".")}


def _cell(value, decimal: str):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value).replace(".", decimal)
    return value


def export_csv(engine: Engine, out_dir: str | Path, locale: str = "fr") -> dict[str, int]:
    """Écrit `<vue>.csv` pour chaque vue ; renvoie le nombre de lignes par vue."""
    if locale not in LOCALES:
        raise ValueError(f"locale inconnue : {locale} (fr ou en)")
    delimiter, decimal = LOCALES[locale]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    create_dw(engine)  # une base antérieure n'a pas encore les tables de la situation courante
    create_views(engine)
    counts = {}
    with engine.connect() as conn:
        for name in VIEWS:
            result = conn.execute(text(f"SELECT * FROM {_prefix(engine)}{name}"))
            rows = result.fetchall()
            with open(out / f"{name}.csv", "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=delimiter, lineterminator="\r\n")
                writer.writerow(result.keys())
                writer.writerows([_cell(v, decimal) for v in row] for row in rows)
            counts[name] = len(rows)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporte les vues de l'entrepôt en CSV")
    parser.add_argument("--out", default="bi/export/")
    parser.add_argument("--locale", choices=sorted(LOCALES), default="fr")
    args = parser.parse_args()
    from ..config import get_settings
    from ..storage.engine import make_engine

    print(export_csv(make_engine(get_settings().storage_url), args.out, args.locale))


if __name__ == "__main__":
    main()
