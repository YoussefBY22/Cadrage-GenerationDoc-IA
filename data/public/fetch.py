"""Corpus public réel (lot T4) : construction du manifeste, téléchargement vérifié, table des licences.

Aucun compte, aucune clé. Deux sources ouvertes :
  * Banque mondiale, Open Knowledge Repository (API DSpace publique) : la licence est lue **document par
    document** (champ dc.rights) ; seuls CC BY 3.0 IGO et CC BY 4.0 sont gardés (les variantes NC/ND sont exclues).
    Paires « Diagnostic-pays systématique (SCD) → Cadre de partenariat-pays (CPF) » du même pays.
  * Union européenne, Office des publications (Cellar, SPARQL public) : documents de travail des services de la
    Commission (analyses d'impact = diagnostic) → propositions (COM = livrable) d'un même dossier, en FR et en EN.
    Licence : décision 2011/833/UE de la Commission (réutilisation, CC BY 4.0).

Usage (depuis la racine du dépôt, avec le venv du backend ; httpx est déjà installé) :
  python data/public/fetch.py manifest      # interroge les API et écrit data/public/manifest.json (réseau)
  python data/public/fetch.py download      # télécharge dans data/public/raw/ et vérifie les SHA-256
  python data/public/fetch.py licences      # régénère le tableau de data/LICENCES.md depuis le manifeste
  python data/public/fetch.py stats         # tailles et comptes du manifeste
Le manifeste (URL, SHA-256, licence, rôle, paire) est versionné ; les fichiers de raw/ ne le sont pas.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
RAW = HERE / "raw"
LICENCES_MD = HERE.parent / "LICENCES.md"
MAX_TOTAL_BYTES = 300 * 1024 * 1024
MAX_FILE_BYTES = 12 * 1024 * 1024
OKR = "https://openknowledge.worldbank.org/server/api/discover/search/objects"
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
OPEN_LICENCES = {  # texte dc.rights exact → URL de la licence ; tout le reste est exclu
    "CC BY 3.0 IGO": "https://creativecommons.org/licenses/by/3.0/igo/",
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
}
EU_LICENCE = "Décision 2011/833/UE (réutilisation, CC BY 4.0)"
EU_LICENCE_URL = "https://eur-lex.europa.eu/eli/dec/2011/833/oj"
UA = "pfe-cadrage-corpus/1.0 (academic research, open data)"
SLEEP = 1.0


def _client() -> httpx.Client:
    return httpx.Client(timeout=90, follow_redirects=True, headers={"User-Agent": UA})


def _md(item: dict, key: str) -> str:
    vals = item["metadata"].get(key) or []
    return vals[0]["value"] if vals else ""


# ----------------------------------------------------------------------------- Banque mondiale
def _okr_search(c: httpx.Client, query: str) -> list[dict]:
    out, page = [], 0
    while True:
        r = c.get(OKR, params={"query": query, "dsoType": "ITEM", "size": 100, "page": page},
                  headers={"Accept": "application/json"})
        r.raise_for_status()
        sr = r.json()["_embedded"]["searchResult"]
        out += [o["_embedded"]["indexableObject"] for o in sr["_embedded"]["objects"]]
        page += 1
        if page >= sr["page"]["totalPages"]:
            return out
        time.sleep(SLEEP)


def _country(item: dict) -> str:
    c = _md(item, "okr.region.country")
    if c:
        return c.split("::")[-1].strip()
    t = _md(item, "dc.title")
    t = re.sub(r"(?i)(systematic country diagnostic|country partnership framework).*", "", t)
    t = re.sub(r"(?i)\b(for|of|the|republic|federal|kingdom|democratic|islamic|people'?s)\b|[-–:,]", " ", t)
    return " ".join(t.split()).lower()


def _txt_url(pdfurl: str) -> str:
    return re.sub(r"\.pdf$", ".txt", pdfurl.replace("/pdf/", "/text/").replace("http://", "https://"))


def _okr_entries(c: httpx.Client) -> list[dict]:
    found: dict[str, list[dict]] = {"scd": [], "cpf": []}
    for role, q in (("scd", 'dc.title:"Systematic Country Diagnostic"'),
                    ("cpf", 'dc.title:"Country Partnership Framework"')):
        for it in _okr_search(c, q):
            lic = _md(it, "dc.rights")
            pdf = _md(it, "okr.pdfurl")
            title = _md(it, "dc.title")
            if lic not in OPEN_LICENCES or not pdf or "/pdf/" not in pdf:
                continue
            if role == "cpf" and re.search(r"(?i)performance and learning|progress report|completion", title):
                continue  # on veut le cadre lui-même, pas un bilan
            found[role].append({
                "id": "wb-" + _md(it, "dc.identifier.uri").rsplit("/", 1)[-1],
                "source": "okr", "title": title, "lang": "en", "country": _country(it),
                "date": _md(it, "dc.date.issued")[:10], "licence": lic,
                "licence_url": _md(it, "dc.rights.uri") or OPEN_LICENCES[lic],
                "page_url": _md(it, "dc.identifier.uri"), "url": _txt_url(pdf), "format": "txt",
                "role": "diagnostic" if role == "scd" else "livrable",
            })
    entries, pair_no = [], 0
    for scd in sorted(found["scd"], key=lambda e: e["date"]):
        cands = [p for p in found["cpf"] if p["country"] == scd["country"]
                 and "pair" not in p and 0 <= int(p["date"][:4] or 0) - int(scd["date"][:4] or 0) <= 4]
        if not cands:
            continue
        cpf = min(cands, key=lambda p: p["date"])
        pair_no += 1
        scd["pair"] = cpf["pair"] = f"wb-pair-{pair_no:02d}"
        entries += [scd, cpf]
    return entries


# ----------------------------------------------------------------------------- UE (Cellar)
_EU_QUERY = """  # __KIND__ : SC = document de travail des services, DC = rapport de la Commission
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?dos ?sc ?pc WHERE {
 ?w1 cdm:resource_legal_id_celex ?sc . ?w1 cdm:work_part_of_dossier ?dos .
 ?w2 cdm:resource_legal_id_celex ?pc . ?w2 cdm:work_part_of_dossier ?dos .
 FILTER(REGEX(STR(?sc),"^520(19|20|21|22)__KIND__0[0-9]{3}$") && REGEX(STR(?pc),"^520(19|20|21|22)PC0[0-9]{3}$"))
} LIMIT 400
"""


def _eu_url(celex: str) -> str:
    return f"https://publications.europa.eu/resource/celex/{celex}"


def _eu_probe(c: httpx.Client, celex: str, lang: str) -> int | None:
    """Taille annoncée de la version `lang` (fra|eng) si elle existe en XHTML, sinon None (sans tout lire)."""
    with c.stream("GET", _eu_url(celex), headers={"Accept": "application/xhtml+xml", "Accept-Language": lang}) as r:
        if r.status_code != 200 or "xhtml" not in r.headers.get("content-type", ""):
            return None
        return int(r.headers.get("content-length") or 100_000)


def _eu_entries(c: httpx.Client, max_pairs: int, kind: str = "SC", start: int = 0) -> list[dict]:
    r = c.get(SPARQL, params={"query": _EU_QUERY.replace("__KIND__", kind)}, headers={"Accept": "text/csv"})
    r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.text)))
    pairs: dict[str, tuple[str, str]] = {}
    for row in rows:  # un seul SWD par proposition (le plus petit numéro = rapport principal)
        key = row["pc"]
        if key not in pairs or row["sc"] < pairs[key][0]:
            pairs[key] = (row["sc"], row["pc"])
    entries, n = [], start
    for sc, pc in sorted(pairs.values(), key=lambda p: p[1])[:max_pairs * 4]:
        if n >= start + max_pairs:
            break
        sizes = {}
        for celex in (sc, pc):
            for lang in ("fra", "eng"):
                sizes[(celex, lang)] = _eu_probe(c, celex, lang)
                time.sleep(SLEEP)
        for lang in ("fra", "eng"):
            a, b = sizes[(sc, lang)], sizes[(pc, lang)]
            if not a or not b or a > MAX_FILE_BYTES or b > MAX_FILE_BYTES or a < 20_000 or b < 20_000:
                continue
            n += 1
            pid = f"eu-pair-{n:02d}"
            for celex, role in ((sc, "diagnostic"), (pc, "livrable")):
                entries.append({
                    "id": f"eu-{celex}-{lang[:2]}", "source": "cellar", "pair": pid,
                    "title": f"CELEX {celex}", "lang": "fr" if lang == "fra" else "en",
                    "country": "UE", "date": f"20{celex[3:5]}", "licence": EU_LICENCE,
                    "licence_url": EU_LICENCE_URL, "page_url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
                    "url": _eu_url(celex), "lang_header": lang, "format": "xhtml", "role": role,
                })
    return entries


# ----------------------------------------------------------------------------- Banque mondiale, versions françaises
WDS = "https://search.worldbank.org/api/v3/wds"


def _okr_licence_by_guid(c: httpx.Client, guid: str) -> tuple[str, str]:
    """(licence, uri de la page OKR) de l'œuvre dont la version française porte ce guid ; ('', '') si inconnue."""
    r = c.get(OKR, params={"dsoType": "ITEM", "query": f"okr.guid:{guid}"}, headers={"Accept": "application/json"})
    r.raise_for_status()
    objs = r.json()["_embedded"]["searchResult"]["_embedded"]["objects"]
    if len(objs) != 1:
        return "", ""
    it = objs[0]["_embedded"]["indexableObject"]
    return _md(it, "dc.rights"), _md(it, "dc.identifier.uri")


def _wb_fr_entries(c: httpx.Client, start: int = 0) -> list[dict]:
    """Versions françaises des SCD, CPF et stratégies-pays ; licence de l'œuvre lue dans l'OKR (CC BY seulement)."""
    found = []
    for docty, role in (("Systematic Country Diagnostic", "diagnostic"), ("Country Partnership Framework", "livrable"),
                        ("Country Assistance Strategy Document", "livrable")):
        r = c.get(WDS, params={"format": "json", "lang_exact": "French", "docty_exact": docty, "rows": 100,
                               "qterm": "*", "fl": "id,docty,display_title,docdt,count,txturl,guid"})
        r.raise_for_status()
        for d in r.json()["documents"].values():
            if not isinstance(d, dict) or not d.get("txturl") or not d.get("guid"):
                continue
            if re.search(r"(?i)executive-?summary|resume|sommaire|annex", d["txturl"] + d.get("display_title", "")):
                continue
            lic, page = _okr_licence_by_guid(c, d["guid"])
            time.sleep(SLEEP)
            if lic not in OPEN_LICENCES:
                continue
            found.append({
                "id": "wbfr-" + d["id"], "source": "okr", "lang": "fr", "country": d.get("count", ""),
                "title": (d.get("display_title") or d["txturl"].rsplit("/", 1)[-1])[:140],
                "date": d.get("docdt", "")[:10], "licence": lic, "licence_url": OPEN_LICENCES[lic],
                "page_url": page, "url": d["txturl"].replace("http://", "https://"), "format": "txt", "role": role})
    out, n = [], start
    used: set[str] = set()
    diag = sorted((f for f in found if f["role"] == "diagnostic"), key=lambda f: f["date"])
    for f in diag:
        cands = [p for p in found if p["role"] == "livrable" and p["country"] == f["country"]
                 and p["id"] not in used and 0 <= int(p["date"][:4] or 0) - int(f["date"][:4] or 0) <= 4]
        if cands:
            p = min(cands, key=lambda x: x["date"])
            n += 1
            f["pair"] = p["pair"] = f"wb-fr-pair-{n:02d}"
            used |= {f["id"], p["id"]}
            out += [f, p]
    for f in found:  # sans partenaire : un groupe d'un seul document (utile à l'entraînement, pas aux paires)
        if f["id"] not in used:
            n += 1
            f["pair"] = f"wb-fr-solo-{n:02d}"
            out.append(f)
    return out


def cmd_manifest(args: argparse.Namespace) -> None:
    with _client() as c:
        old_all = json.loads(MANIFEST.read_text("utf-8"))["documents"] if MANIFEST.exists() else []
        if args.only == "wb-fr":
            have = {o["id"] for o in old_all}
            add = [e for e in _wb_fr_entries(c, start=0) if e["id"] not in have]
            MANIFEST.write_text(json.dumps({"version": 1, "documents": old_all + add}, ensure_ascii=False, indent=1)
                                + chr(10), encoding="utf-8")
            print(f"{len(add)} documents ajoutés")
            return
        if args.only == "eu-dc":  # complément : rapports de la Commission (DC) → propositions, pour plus de français
            start = sum(1 for o in old_all if o["source"] == "cellar" and o["role"] == "livrable")
            new = [e for e in _eu_entries(c, args.eu_pairs, "DC", start)
                   if e["id"] not in {o["id"] for o in old_all}]
            MANIFEST.write_text(json.dumps({"version": 1, "documents": old_all + new}, ensure_ascii=False, indent=1)
                                + chr(10), encoding="utf-8")
            print(f"{len(new)} documents ajoutés")
            return
        entries = ([] if args.only == "eu" else _okr_entries(c)) + ([] if args.only == "okr" else _eu_entries(c, args.eu_pairs))
    old = {e["id"]: e for e in json.loads(MANIFEST.read_text("utf-8"))["documents"]} if MANIFEST.exists() else {}
    if args.only != "all":  # on garde les entrées de l'autre source
        keep = "cellar" if args.only == "okr" else "okr"
        entries = [o for o in old.values() if o["source"] == keep] + entries
    for e in entries:  # on conserve les empreintes déjà calculées
        if e["id"] in old:
            e.update({k: old[e["id"]][k] for k in ("sha256", "bytes", "pages", "collected") if k in old[e["id"]]})
    MANIFEST.write_text(json.dumps({"version": 1, "documents": entries}, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(f"{len(entries)} documents dans {MANIFEST}")


# ----------------------------------------------------------------------------- téléchargement
def _fetch(c: httpx.Client, e: dict) -> bytes:
    headers = {"Accept": "application/xhtml+xml", "Accept-Language": e["lang_header"]} if e["source"] == "cellar" else {}
    r = c.get(e["url"], headers=headers)
    r.raise_for_status()
    return r.content


def cmd_download(args: argparse.Namespace) -> None:
    data = json.loads(MANIFEST.read_text("utf-8"))
    RAW.mkdir(parents=True, exist_ok=True)
    total, bad = 0, 0
    with _client() as c:
        for e in data["documents"]:
            path = RAW / f"{e['id']}.{e['format']}"
            if not path.exists():
                try:
                    blob = _fetch(c, e)
                except httpx.HTTPError as exc:
                    print(f"  ÉCHEC {e['id']}: {exc}", file=sys.stderr)
                    e["failed"] = True
                    bad += 1
                    continue
                if len(blob) > MAX_FILE_BYTES or total + len(blob) > MAX_TOTAL_BYTES:
                    print(f"  ignoré (taille) {e['id']}", file=sys.stderr)
                    e["failed"] = True
                    continue
                path.write_bytes(blob)
                time.sleep(SLEEP)
            blob = path.read_bytes()
            total += len(blob)
            digest = hashlib.sha256(blob).hexdigest()
            if e.get("sha256") and e["sha256"] != digest:
                print(f"  SOMME DIFFÉRENTE {e['id']} (le document source a changé)", file=sys.stderr)
                bad += 1
            e.setdefault("sha256", digest)
            e["bytes"] = len(blob)
            e.setdefault("collected", time.strftime("%Y-%m-%d"))
            e.pop("failed", None)
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(data['documents'])} documents, {total / 1e6:.1f} Mo, anomalies : {bad}")


# ----------------------------------------------------------------------------- licences
BEGIN, END = "<!-- T4:BEGIN (généré par data/public/fetch.py licences) -->", "<!-- T4:END -->"


def cmd_licences(_: argparse.Namespace) -> None:
    docs = [d for d in json.loads(MANIFEST.read_text("utf-8"))["documents"] if d.get("sha256")]
    rows = ["| Fichier (`data/public/raw/`) | Source | Licence | Date de collecte | Remarque |", "|---|---|---|---|---|"]
    for d in docs:
        rows.append(f"| `{d['id']}.{d['format']}` | [{d['title'][:80].replace('|', '/')}]({d['page_url']}) | "
                    f"[{d['licence']}]({d['licence_url']}) | {d.get('collected', '')} | {d['role']}, {d['lang']}, paire {d['pair']} ; "
                    f"SHA-256 `{d['sha256'][:12]}…` |")
    block = f"{BEGIN}\n" + "\n".join(rows) + f"\n{END}"
    text = LICENCES_MD.read_text("utf-8")
    text = re.sub(f"{re.escape(BEGIN)}.*?{re.escape(END)}", lambda _m: block, text, flags=re.S)
    LICENCES_MD.write_text(text, encoding="utf-8")
    print(f"{len(docs)} lignes écrites dans {LICENCES_MD}")


def cmd_stats(_: argparse.Namespace) -> None:
    docs = json.loads(MANIFEST.read_text("utf-8"))["documents"]
    print(len(docs), "documents,", sum(d.get("bytes", 0) for d in docs) / 1e6, "Mo")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("manifest")
    m.add_argument("--eu-pairs", type=int, default=30)
    m.add_argument("--only", choices=["okr", "eu", "eu-dc", "wb-fr", "all"], default="all")
    m.set_defaults(fn=cmd_manifest)
    sub.add_parser("download").set_defaults(fn=cmd_download)
    sub.add_parser("licences").set_defaults(fn=cmd_licences)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
