"""Sources publiques du pilote v3 : licence et preuve obligatoires (voir docs/lots/DATA.md).

Chaque entrée dit d'où vient le document, sous quelle licence il est réutilisable, et où on le lit.
Un document sans licence ou sans preuve n'entre pas : ``check_manifest`` le refuse.
Le partage entraînement / test se fait PAR DOCUMENT : ``test`` fixe le côté de chaque document.
"""

from __future__ import annotations

import hashlib
import subprocess
import urllib.request
from pathlib import Path

ECA_LICENCE = "CC BY 4.0 (Cour des comptes européenne, décision n° 6-2019)"
ECA_PREUVE = "https://www.eca.europa.eu/fr/legal-notice"
ECA_EXTRAIT = ("« le contenu de ce site internet fait l'objet d'une licence Creative Commons Attribution 4.0 "
               "International (CC BY 4.0) » ; même mention dans la page de mentions légales de chaque rapport")
LOV2 = "Licence Ouverte 2.0 (Etalab)"
LOV2_EXTRAIT = "champ « license » = lov2 dans la fiche data.gouv.fr du jeu de données (API publique)"
ECA_REP_NOTE = ("réponses de la Commission publiées par la Cour : le PDF ne porte aucune mention de licence ; "
                "couvert par la mention du site de la Cour et par la décision 2011/833/UE de la Commission "
                "(CC BY 4.0), à confirmer")


def _eca(sid: str, titre: str, test: bool, familles: str) -> dict:
    return {"id": f"eca-{sid.lower()}", "titre": titre, "editeur": "Cour des comptes européenne",
            "url": f"https://www.eca.europa.eu/ECAPublications/{sid}/{sid}_FR.pdf",
            "licence": ECA_LICENCE, "preuve_url": ECA_PREUVE, "preuve_extrait": ECA_EXTRAIT,
            "famille": familles, "test": test}


def _rep(sid: str, titre: str, test: bool) -> dict:
    return {"id": f"eca-rep-{sid.lower()}", "titre": f"Réponses de la Commission : {titre}",
            "editeur": "Commission européenne (publié par la Cour des comptes européenne)",
            "url": f"https://www.eca.europa.eu/Lists/ECAReplies/COM-Replies-{sid}/COM-Replies-{sid}_FR.pdf",
            "licence": ECA_LICENCE + " ; Commission : décision 2011/833/UE, CC BY 4.0",
            "preuve_url": ECA_PREUVE, "preuve_extrait": ECA_REP_NOTE, "famille": "divergences",
            "test": test}


def _dg(did: str, titre: str, editeur: str, slug: str, url: str, test: bool, famille: str) -> dict:
    return {"id": did, "titre": titre, "editeur": editeur, "url": url, "licence": LOV2,
            "preuve_url": f"https://www.data.gouv.fr/api/1/datasets/{slug}/", "preuve_extrait": LOV2_EXTRAIT,
            "famille": famille, "test": test}


_DINUM25 = "accord-cadre-interministeriel-realisation-de-services-publics-numeriques-en-mode-produit-agile-pilote-par-limpact"
_STATIC = "https://static.data.gouv.fr/resources/"

SOURCES: dict[str, dict] = {s["id"]: s for s in [
    _eca("SR-2024-26", "Rapport spécial 26/2024 : intégration des ressortissants de pays tiers (FAMI)", True,
         "feuille de route, constats"),
    _eca("SR-2024-27", "Rapport spécial 27/2024 : lutte contre les régimes fiscaux dommageables", False,
         "feuille de route, constats"),
    _eca("SR-2024-28", "Rapport spécial 28/2024 : respect du droit de l'Union", False,
         "feuille de route, constats"),
    _rep("SR-2024-27", "rapport spécial 27/2024", False),
    _rep("SR-2026-13", "rapport spécial 13/2026 (marché unique des services)", True),
    _dg("dinum-cctp-2025", "CCTP, accord-cadre « services numériques en mode produit » (DINUM, 2025)",
        "Direction interministérielle du numérique (beta.gouv.fr)", _DINUM25,
        _STATIC + _DINUM25 + "/20260430-124236/cctp-marche-produit.pdf", False, "cdc, tdr"),
    _dg("dinum-cctp-securite-2025", "Annexe 1 du CCTP : obligations et exigences de sécurité (DINUM, 2025)",
        "Direction interministérielle du numérique (beta.gouv.fr)", _DINUM25,
        _STATIC + _DINUM25 + "/20260430-124436/cctp-clauses-de-securite-annexe-1.pdf", True, "cdc"),
    _dg("dinum-cctp-2021", "CCTP 21-BAM-048, services numériques en mode produit (DINUM, 2021)",
        "Direction interministérielle du numérique (beta.gouv.fr)",
        "realisation-de-services-publics-numeriques-en-mode-produit-coordonnes-par-le-programme-interministeriel-beta-gouv",
        _STATIC + "realisation-de-services-publics-numeriques-en-mode-produit-coordonnes-par-le-programme-"
        "interministeriel-beta-gouv/20210616-100741/cctp-21-bam-048-modifi-0206.pdf", True, "tdr"),
    _dg("ccas-rochefort-cdc-2025", "Cahier des charges : portage de repas en liaison froide (CCAS de Rochefort, 2025)",
        "Centre communal d'action sociale de Rochefort",
        "marche-de-service-livraison-en-liaison-froide-de-repas-a-domicile-de-personnes-dependantes-avec-veille-sociale",
        _STATIC + "marche-de-service-livraison-en-liaison-froide-de-repas-a-domicile-de-personnes-dependantes-"
        "avec-veille-sociale/20250429-084900/cahier-des-charges-2025.pdf", False, "cdc"),
]}

REQUIRED = ("id", "titre", "editeur", "url", "licence", "preuve_url", "preuve_extrait", "test")


def check_manifest(sources: dict[str, dict] | None = None) -> list[str]:
    """Liste des défauts : licence ou preuve manquante, preuve non HTTP(S)."""
    problems: list[str] = []
    for sid, s in (sources or SOURCES).items():
        for k in REQUIRED:
            if s.get(k) in (None, ""):
                problems.append(f"{sid} : champ « {k} » manquant")
        if not str(s.get("preuve_url", "")).startswith("https://"):
            problems.append(f"{sid} : la preuve de licence doit être une adresse https")
        if "licence" in s and not any(w in s["licence"].lower() for w in ("cc by", "licence ouverte", "etalab")):
            problems.append(f"{sid} : licence non reconnue comme libre : {s['licence']}")
    return problems


def source_text(sources_dir: Path, sid: str) -> str:
    """Texte extrait du PDF (``<id>.txt``) ; refuse un document absent ou hors manifeste."""
    if sid not in SOURCES:
        raise KeyError(f"document hors manifeste (licence inconnue) : {sid}")
    p = Path(sources_dir) / f"{sid}.txt"
    if not p.exists():
        raise FileNotFoundError(f"{p} : lancer d'abord `python -m training.dataset.v3_sources --fetch`")
    return p.read_text(encoding="utf-8")


def fetch(sources_dir: Path, ids: list[str] | None = None) -> dict[str, str]:
    """Télécharge les PDF (User-Agent générique) puis extrait le texte avec ``pdftotext``. Renvoie les SHA-256."""
    problems = check_manifest()
    if problems:
        raise ValueError("manifeste invalide : " + "; ".join(problems))
    out: dict[str, str] = {}
    sources_dir = Path(sources_dir)
    sources_dir.mkdir(parents=True, exist_ok=True)
    for sid in ids or list(SOURCES):
        req = urllib.request.Request(SOURCES[sid]["url"], headers={"User-Agent": "Mozilla/5.0 (compatible; research-client)"})
        pdf = sources_dir / f"{sid}.pdf"
        pdf.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(pdf), str(sources_dir / f"{sid}.txt")], check=True)
        out[sid] = hashlib.sha256(pdf.read_bytes()).hexdigest()
    return out


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources-dir", type=Path, required=True)
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()
    if a.fetch:
        for sid, h in fetch(a.sources_dir).items():
            print(sid, h)
    else:
        print("\n".join(check_manifest()) or "manifeste valide")


if __name__ == "__main__":
    main()
