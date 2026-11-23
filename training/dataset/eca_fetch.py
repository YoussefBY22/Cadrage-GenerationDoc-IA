"""Téléchargement des rapports spéciaux de la Cour des comptes européenne (PDF publics, CC BY 4.0) et de leurs réponses.

Seuls les PDF publics sont lus ; User-Agent générique ; pause entre deux requêtes. Un rapport ou une réponse
absente (404) est simplement ignoré. Le texte est extrait avec ``pdftotext`` (UTF-8, mise en page conservée).

    python -m training.dataset.eca_fetch --out-dir DOSSIER --years 2023 2024 2025 2026
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

UA = "Mozilla/5.0 (compatible; research-client)"
ECA_LICENCE = "CC BY 4.0 (Cour des comptes européenne, décision n° 6-2019)"
ECA_PREUVE = "https://www.eca.europa.eu/fr/legal-notice"
PAUSE = 0.8


def report_url(year: int, number: int) -> str:
    sid = f"SR-{year}-{number:02d}"
    return f"https://www.eca.europa.eu/ECAPublications/{sid}/{sid}_FR.pdf"


def reply_url(year: int, number: int) -> str:
    sid = f"SR-{year}-{number:02d}"
    return f"https://www.eca.europa.eu/Lists/ECAReplies/COM-Replies-{sid}/COM-Replies-{sid}_FR.pdf"


def _curl(url: str, dest: Path | None) -> bool:
    cmd = ["curl", "-sSf", "-L", "-A", UA, "-o", str(dest) if dest else "NUL", url]
    ok = subprocess.run(cmd, capture_output=True).returncode == 0
    time.sleep(PAUSE)
    return ok


def fetch_one(out_dir: Path, doc_id: str, url: str) -> dict | None:
    pdf = out_dir / f"{doc_id}.pdf"
    if not pdf.exists() and not _curl(url, pdf):
        pdf.unlink(missing_ok=True)
        return None
    subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(pdf), str(out_dir / f"{doc_id}.txt")], check=True)
    return {"id": doc_id, "url": url, "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()}


def fetch(out_dir: Path, years: list[int], numbers: range = range(1, 33)) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for y in years:
        for n in numbers:
            rep = fetch_one(out_dir, f"eca-sr-{y}-{n:02d}", report_url(y, n))
            if rep is None:
                continue
            row = {**rep, "kind": "rapport", "year": y, "number": n, "licence": ECA_LICENCE, "preuve": ECA_PREUVE}
            ans = fetch_one(out_dir, f"eca-rep-sr-{y}-{n:02d}", reply_url(y, n))
            row["reponse"] = ({**ans, "licence": ECA_LICENCE + " ; Commission : décision 2011/833/UE, CC BY 4.0"}
                              if ans else None)
            manifest.append(row)
            print(row["id"], "réponse" if ans else "sans réponse", flush=True)
    (out_dir / "eca-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--years", type=int, nargs="+", default=[2023, 2024, 2025, 2026])
    a = ap.parse_args()
    fetch(a.out_dir, a.years)


if __name__ == "__main__":
    main()
