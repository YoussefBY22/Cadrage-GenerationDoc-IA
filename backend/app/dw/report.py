"""Rapport de pilotage DOCX ou PDF, avec les règles du tableau de bord (docs/14).

    python -m app.dw.report --out rapport.pdf
    python -m app.dw.report --out client.docx --audience client --client "Nom du client"

Filtres : --client, --type, --consultant, --since, --until. La période porte sur les flux
(soumissions, approbations, générations) ; la file, les recommandations et la prédiction décrivent
toujours la situation à la date des données, comme dans Power BI.

`--audience client` exige un client : le document ne contient alors ni personne, ni autre client,
ni modèle entraîné sur l'historique des autres clients.
"""

import argparse
import shutil
import statistics
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from sqlalchemy import Engine, text

from ..export.common import ExportUnavailable
from ..export.pdf_export import TIMEOUT_SECONDS, soffice_binary
from . import pilotage
from .etl import TYPES
from .views_sql import _prefix

ALL = "Tous"
NOT_MEASURED = "Non mesuré"
INTERNAL, CLIENT = "interne", "client"
SIMULATION = "Simulation sur données inventées : aucun de ces chiffres ne décrit une mission réelle."


@dataclass(frozen=True)
class Scope:
    client: str | None = None
    type_code: str | None = None
    consultant: str | None = None
    since: date | None = None
    until: date | None = None
    audience: str = INTERNAL

    def __post_init__(self):
        if self.audience not in (INTERNAL, CLIENT):
            raise ValueError(f"lecteur inconnu : {self.audience}")
        if self.audience == CLIENT and not self.client:
            raise ValueError("un rapport destiné à un client doit être filtré sur ce client")
        if self.audience == CLIENT and self.consultant:
            raise ValueError("un rapport destiné à un client ne porte pas sur une personne")
        if self.type_code and self.type_code not in TYPES:
            raise ValueError(f"type de livrable inconnu : {self.type_code}")
        if self.since and self.until and self.since > self.until:
            raise ValueError("la période commence après sa fin")


def _key(d: date | None) -> int | None:
    return d.year * 10000 + d.month * 100 + d.day if d else None


def _half_up(x: float, decimals: int = 0) -> Decimal:
    """Arrondi au plus proche, demi vers le haut : celui de DAX, pas l'arrondi bancaire de Python."""
    return Decimal(str(x)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def pct(x: float | None) -> str:
    return "—" if x is None else f"{_half_up(Decimal(str(x)) * 100)} %"


def num(x: float | None, decimals: int = 0) -> str:
    return "—" if x is None else str(_half_up(x, decimals)).replace(".", ",")


def count(n: int, singular: str, plural: str) -> str:
    return f"{n} {plural if n > 1 else singular}"


def rate(part: int, whole: int) -> str:
    """Un taux va toujours avec son effectif, et disparaît sous l'effectif minimal."""
    if whole < pilotage.MIN_SAMPLE:
        return f"{part} sur {whole} (effectif insuffisant pour un taux)"
    return f"{pct(part / whole)} ({part} sur {whole})"


def collect(engine: Engine, scope: Scope) -> dict:
    """Toutes les données du rapport, déjà filtrées."""
    p = _prefix(engine)
    with engine.connect() as c:
        def rows(view: str) -> list[dict]:
            return [dict(r._mapping) for r in c.execute(text(f"SELECT * FROM {p}{view}"))]

        deliverables, people = rows("v_deliverable"), rows("v_person")
        outcomes, actions = rows("v_outcome"), rows("v_action")
        generations, forecasts = rows("v_generation"), rows("v_forecast")

    client_key = author_key = None
    type_key = TYPES[scope.type_code][0] if scope.type_code else None
    if scope.client:
        keys = {d["client_key"] for d in deliverables if d["client_name"] == scope.client}
        if len(keys) != 1:
            raise ValueError(f"client introuvable : {scope.client}")
        client_key = keys.pop()
    if scope.consultant:
        keys = {u["user_key"] for u in people if u["user_label"] == scope.consultant}
        if len(keys) != 1:
            raise ValueError(f"consultant introuvable : {scope.consultant}")
        author_key = keys.pop()

    since, until = _key(scope.since) or 0, _key(scope.until) or 99999999

    def dated(key) -> bool:
        return key is not None and since <= key <= until

    ds = [d for d in deliverables
          if client_key in (None, d["client_key"]) and type_key in (None, d["type_key"])
          and author_key in (None, d["author_key"])]
    ids = {d["deliverable_id"] for d in ds}
    missions = {d["mission_key"] for d in ds}
    approved = [d for d in ds if d["state"] == "approved" and dated(d["approved_date_key"])]
    measured = [d for d in approved if d["citations_total"] is not None]
    first = [d for d in ds if d["first_rejected"] is not None and dated(d["submitted_date_key"])]
    outs = [o for o in outcomes if o["deliverable_id"] in ids and dated(o["date_key"])]
    written = [o for o in outs if not o["was_refused"]]
    gens = [g for g in generations
            if g["status"] == "ok" and g["type_code"] != "findings" and dated(g["date_key"])
            and g["mission_key"] in missions and (not scope.type_code or g["type_code"] == scope.type_code)
            and author_key in (None, g["author_key"])]
    delays = [float(d["delay_hours"]) for d in approved if d["delay_hours"] is not None]
    forecast = next((f for f in forecasts if f["client_key"] == client_key
                     and f["type_key"] == type_key and f["author_key"] == author_key
                     and f["reviewer_key"] is None), None)

    def total(items, key):
        return sum(x[key] or 0 for x in items)

    queue = [d for d in ds if d["state"] == "in_review"]
    simulated = any(d["is_demo"] for d in ds)
    if simulated:  # des données inventées ne mesurent aucun risque
        queue = [d | {"risk": None} for d in queue]
    return {
        "scope": scope,
        "as_of": max((d["as_of"] for d in ds), default=None),
        "simulated": simulated,
        "todo": sum(d["state"] in ("draft", "rejected") for d in ds),
        "returned": sum(bool(d["returned"]) for d in ds),
        "to_review": len(queue),
        "overdue": sum(d["state_age_hours"] > pilotage.REVIEW_OVERDUE_HOURS for d in queue),
        "blocking_draft": total([d for d in ds if d["state"] in ("draft", "rejected")], "blocking_open"),
        "blocking_review": total(queue, "blocking_open"),
        "approved": len(approved), "measured": len(measured),
        "invalid_left": total(measured, "citations_invalid") if measured else None,
        "citations_left": total(measured, "citations_total"),
        "invalid_detected": total(gens, "citations_total") - total(gens, "citations_valid"),
        "citations_generated": total(gens, "citations_total"),
        "verified": total(gens, "sentences_verified"), "generated": total(gens, "sentences_total"),
        "unchanged": sum(bool(o["unchanged"]) for o in written), "written": len(written),
        "delay": statistics.median(delays) if delays else None, "delays": len(delays),
        "rejected_first": sum(bool(d["first_rejected"]) for d in first), "decided_first": len(first),
        "recommendations": pilotage.recommendations(ds, actions),
        "forecast": forecast,
        "queue": sorted(queue, key=lambda d: -pilotage.queue_priority(d["state_age_hours"], d["risk"])),
        "people": {u["user_key"]: u["user_label"] for u in people},
    }


def h7_rows(r: dict) -> list[tuple[str, str, str, str]]:
    """Critère, cible, mesure, verdict. Jamais de verdict sur ce qui n'est pas mesuré."""
    if r["simulated"]:
        return [("Citations sans source dans les livrables approuvés", "0", "—", "Non mesuré"),
                ("Sections acceptées sans retouche", f"≥ {pct(pilotage.H7_REUSABLE)}", "—", "Non mesuré")]
    left = r["invalid_left"]
    if left is None:
        verdict, value = "Non mesuré", "—"
    else:
        value = f"{left} sur {r['citations_left']} citations, {r['measured']} livrables approuvés"
        if left > pilotage.H7_INVALID_LEFT:
            verdict = "Non atteint"
        elif r["measured"] < r["approved"]:
            verdict = "Non mesuré en totalité"
        elif r["measured"] < pilotage.MIN_SAMPLE:
            verdict = "Effectif insuffisant"
        else:
            verdict = "Atteint"
    rows = [("Citations sans source dans les livrables approuvés", "0", value, verdict)]
    if r["written"] < pilotage.MIN_SAMPLE:
        verdict = "Effectif insuffisant"
    elif r["unchanged"] / r["written"] >= pilotage.H7_REUSABLE:
        verdict = "Atteint (approximation)"
    else:
        verdict = "Non atteint (approximation)"
    rows.append(("Sections acceptées sans retouche", f"≥ {pct(pilotage.H7_REUSABLE)}",
                 rate(r["unchanged"], r["written"]), verdict))
    return rows


def forecast_lines(r: dict) -> list[str]:
    f = r["forecast"]
    if f is None or f["status"] == "insufficient":
        return ["Historique insuffisant pour prévoir la charge de relecture de ce périmètre."]
    if f["status"] == "not_better":
        return [("Aucune prévision publiée : sur l'historique, la méthode ne fait pas mieux que la "
                "référence naïve (répéter les deux dernières semaines).")]
    lines = [
        (f"{num(f['point'])} soumissions attendues dans les 2 prochaines semaines (intervalle de "
        f"{pct(pilotage.INTERVAL)} : {num(f['low'])} à {num(f['high'])}), en plus des "
        f"{r['to_review']} déjà en attente."),
        (f"Méthode : moyenne des {pilotage.WINDOW_WEEKS} dernières semaines × 2. Historique : "
        f"{f['events']} soumissions sur {f['weeks']} semaines. Sur {f['origins']} prévisions "
        f"rétrospectives, elle se trompe de {num(f['mae'], 1)} soumissions en moyenne, contre "
        f"{num(f['mae_naive'], 1)} pour la référence naïve.")]
    return [lines[0], "Fiabilité non mesurée : volumes inventés."] if r["simulated"] else lines


def limits(r: dict) -> list[str]:
    out = [
        ("H7 raisonne par phrase et l'entrepôt par section : « sans retouche » est une approximation "
        "plus sévère."),
        ("Une citation « sans source » désigne une source absente du dossier. Qu'une source existe ne "
        "prouve pas qu'elle soutient la phrase."),
        ("Une phrase modifiée par le consultant n'est pas revérifiée dans l'entrepôt : seule sa source "
        "est contrôlée."),
        f"Aucun taux n'est affiché sous {pilotage.MIN_SAMPLE} cas.",
        ("La file, les recommandations et la prédiction décrivent la situation à la date des données, "
        "quelle que soit la période choisie.")]
    if r["simulated"]:
        out.insert(0, SIMULATION)
    return out


def _fr_date(iso: str | None) -> str:
    if not iso:
        return "date inconnue"
    y, m, d = iso[:10].split("-")
    return f"{d}/{m}/{y}"


def render_docx(r: dict, path: Path) -> None:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    ink, grey, white = RGBColor(0x2E, 0x2E, 0x38), RGBColor(0x74, 0x74, 0x80), RGBColor(0xFF, 0xFF, 0xFF)
    scope: Scope = r["scope"]
    doc = Document()
    doc.core_properties.author = "Cadrage"
    doc.core_properties.title = "Rapport de pilotage"
    doc.core_properties.comments = ""
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(1.8)
    sec.top_margin = sec.bottom_margin = Cm(1.5)
    body = doc.styles["Normal"]
    body.font.name, body.font.size = "Segoe UI", Pt(9.5)
    body.paragraph_format.space_after = Pt(3)

    def para(value: str, size: float = 9.5, bold: bool = False, color=ink, before: float = 0):
        p = doc.add_paragraph()
        run = p.add_run(value)
        run.bold, run.font.size, run.font.color.rgb = bold, Pt(size), color
        p.paragraph_format.space_before = Pt(before)
        return p

    def edge(p, side: str, width: str) -> None:
        box, line = OxmlElement("w:pBdr"), OxmlElement(f"w:{side}")
        for k, v in (("val", "single"), ("sz", width), ("space", "4"), ("color", "FFE600")):
            line.set(qn(f"w:{k}"), v)
        box.append(line)
        p._p.get_or_add_pPr().append(box)

    def heading(value: str) -> None:
        p = para(value, 12.5, True, before=10)
        p.paragraph_format.keep_with_next = True
        edge(p, "bottom", "12")

    def table(header: list[str], rows: list[tuple], widths: list[float]) -> None:
        t = doc.add_table(rows=0, cols=len(header))
        t.style, t.autofit = "Table Grid", False
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        grid = t._tbl.tblGrid.gridCol_lst
        for column, width in zip(grid, widths, strict=True):
            column.w = Cm(width)
        for i, values in enumerate([tuple(header), *rows]):
            row = t.add_row()
            props = row._tr.get_or_add_trPr()
            props.append(OxmlElement("w:cantSplit"))
            if not i:
                props.append(OxmlElement("w:tblHeader"))
            for cell, value, width in zip(row.cells, values, widths, strict=True):
                cell.width = Cm(width)
                run = cell.paragraphs[0].add_run(str(value))
                run.bold, run.font.size = not i, Pt(8.5)
                run.font.color.rgb = ink if i else white
                if not i:
                    shade = OxmlElement("w:shd")
                    shade.set(qn("w:val"), "clear")
                    shade.set(qn("w:fill"), "2E2E38")
                    cell._tc.get_or_add_tcPr().append(shade)

    internal = scope.audience == INTERNAL
    edge(para("Cadrage · rapport de pilotage", 19, True), "left", "36")
    period = ("tout l'historique" if not (scope.since or scope.until)
              else f"du {_fr_date(scope.since.isoformat()) if scope.since else 'début'} "
                   f"au {_fr_date(scope.until.isoformat()) if scope.until else 'dernier jour'}")
    who = f"consultant : {scope.consultant or ALL} · " if internal else ""
    kind = TYPES[scope.type_code][1] if scope.type_code else ALL
    para(f"Situation au {_fr_date(r['as_of'])} · client : {scope.client or ALL} · type : {kind} · "
         f"{who}période : {period}", 9, color=grey)
    if r["simulated"]:
        para(SIMULATION, 9.5, True, RGBColor(0xB4, 0x23, 0x2F), before=4)

    heading("Synthèse")
    waiting = count(r["to_review"], "livrable attend", "livrables attendent")
    para(f"{waiting} une relecture, dont {r['overdue']} depuis plus de "
         f"{pilotage.REVIEW_OVERDUE_HOURS} h. Chez les consultants : "
         f"{count(r['todo'], 'livrable', 'livrables')}, dont "
         f"{count(r['returned'], 'renvoi', 'renvois')} à reprendre.")
    if r["recommendations"]:
        top = r["recommendations"][0]
        para(f"Priorité : {top['action']} ({top['finding']}.)")
    para(forecast_lines(r)[0])

    heading("Recommandations prioritaires")
    if r["recommendations"]:
        table(["", "Constat", "Seuil", "Pour", "Action"],
              [(str(i), x["finding"], x["threshold"], x["actor"], x["action"])
               for i, x in enumerate(r["recommendations"], 1)], [0.6, 4.4, 3.9, 2.2, 6.3])
    else:
        para("Aucune règle ne se déclenche sur ce périmètre.")

    heading("Critères de réussite (hypothèse H7)")
    table(["Critère", "Cible", "Mesure", "Verdict"], h7_rows(r), [6.0, 1.7, 6.0, 3.7])

    heading("Indicateurs")
    delay = ("effectif insuffisant" if r["delays"] < pilotage.MIN_SAMPLE
             else f"{num(r['delay'], 1)} h ({r['delays']} livrables)")
    table(["Indicateur", "Valeur", "Décision liée"], [
        ("Livrables à valider", f"{r['to_review']}, dont {r['overdue']} en retard",
         "Qui relit quoi aujourd'hui"),
        ("Délai médian de validation", delay, "Renforcer ou répartir la relecture"),
        ("Renvois à la première relecture", rate(r["rejected_first"], r["decided_first"]),
         "Revoir la préparation avant soumission"),
        ("Phrases bloquantes à vérifier", f"{r['blocking_review']} en relecture",
         "Ce qui se vérifie en premier"),
        ("Phrases bloquantes à corriger", f"{r['blocking_draft']} chez les consultants",
         "Ce qui se corrige avant de soumettre"),
        ("Phrases vérifiées à la génération", NOT_MEASURED if r["simulated"] else rate(r["verified"], r["generated"]),
         "Effort de relecture à prévoir"),
        ("Citations sans source détectées avant relecture",
         NOT_MEASURED if r["simulated"] else rate(r["invalid_detected"], r["citations_generated"]),
         "Régler la recherche ou le modèle"),
    ], [6.4, 5.6, 5.4])

    heading("Prédiction : charge de relecture")
    for line in forecast_lines(r):
        para(line)
    f = r["forecast"]
    if internal and f and f["risk_status"] == "ok" and not r["simulated"]:
        para(f"Le risque de renvoi vient de l'historique global : taux observé selon la présence d'une "
             f"phrase bloquante. Sur {f['risk_tested']} cas rétrospectifs, score de Brier "
             f"{num(f['risk_brier'], 3)}, contre {num(f['risk_brier_naive'], 3)} pour le taux global.")

    if internal and r["queue"]:
        heading("File à valider, par priorité (jours d'attente × (1 + risque))")
        table(["Mission", "Consultant", "Attente", "Bloquantes", "Risque de renvoi (intervalle, n)"], [
            (d["mission_name"], r["people"].get(d["author_key"], "—"),
             f"{num(d['state_age_hours'] / 24, 1)} j",
             "—" if d["blocking_open"] is None else d["blocking_open"],
             "non estimé" if d["risk"] is None else
             f"{pct(d['risk'])} ({pct(d['risk_low'])} à {pct(d['risk_high'])}, n = {d['risk_n']})")
            for d in r["queue"][:12]], [4.4, 4.0, 1.8, 2.1, 5.1])
        if len(r["queue"]) > 12:
            para(f"… et {len(r['queue']) - 12} autres livrables.", color=grey)

    heading("Limites")
    for line in limits(r):
        para("• " + line, 8.5, color=grey)
    doc.save(str(path))


def write_report(engine: Engine, scope: Scope, out: str | Path) -> Path:
    """Écrit le rapport ; le format suit l'extension (.docx ou .pdf)."""
    out = Path(out)
    suffix = out.suffix.lower()
    if suffix not in (".docx", ".pdf"):
        raise ValueError("format attendu : .docx ou .pdf")
    data = collect(engine, scope)
    out.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".docx":
        render_docx(data, out)
        return out
    binary = soffice_binary()
    if binary is None:
        raise ExportUnavailable("LibreOffice (soffice) est absent : utiliser une sortie .docx")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "rapport.docx"
        render_docx(data, src)
        try:
            subprocess.run(
                [binary, f"-env:UserInstallation={(Path(tmp) / 'profile').as_uri()}", "--headless",
                 "--convert-to", "pdf", "--outdir", tmp, str(src)],
                check=True, timeout=TIMEOUT_SECONDS, capture_output=True, cwd=tmp)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            raise ExportUnavailable(f"conversion PDF échouée : {type(exc).__name__}") from exc
        shutil.move(str(src.with_suffix(".pdf")), str(out))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Produit le rapport de pilotage (DOCX ou PDF)")
    parser.add_argument("--out", default="rapport-pilotage.pdf", help="fichier .pdf ou .docx")
    parser.add_argument("--audience", choices=(INTERNAL, CLIENT), default=INTERNAL)
    parser.add_argument("--client", help="nom exact du client (obligatoire si --audience client)")
    parser.add_argument("--type", dest="type_code", choices=sorted(TYPES))
    parser.add_argument("--consultant", help="nom affiché exact")
    parser.add_argument("--since", type=date.fromisoformat, help="aaaa-mm-jj")
    parser.add_argument("--until", type=date.fromisoformat, help="aaaa-mm-jj")
    args = parser.parse_args()
    from ..config import get_settings
    from ..storage.engine import make_engine

    try:
        scope = Scope(args.client, args.type_code, args.consultant, args.since, args.until, args.audience)
        print(write_report(make_engine(get_settings().storage_url), scope, args.out))
    except (ValueError, ExportUnavailable) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
