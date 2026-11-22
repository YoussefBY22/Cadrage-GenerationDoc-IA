"""Génère le projet Power BI (PBIP) : modèle sémantique TMDL + rapport PBIR (5 pages).

Usage : python bi/pbip/build_pbip.py   (idempotent ; réécrit CadrageIA.SemanticModel et CadrageIA.Report)
Le thème vient de bi/theme/cadrage-ey.json. Les mesures viennent de la liste MEASURES ci-dessous, qui est aussi
écrite dans bi/measures.dax (une seule source de vérité).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BI = ROOT.parent
SM = ROOT / "CadrageIA.SemanticModel"
RP = ROOT / "CadrageIA.Report"
DEFAULT_CSV = r"C:\Users\youss\Desktop\PFE-IA-Cadrage\bi\export"

# ---------------------------------------------------------------- tables (colonne, type)
I, D, S, DT = "int64", "double", "string", "dateTime"
TABLES: dict[str, list[tuple[str, str]]] = {
    "v_generation": [
        ("generation_key", I), ("run_id", S), ("date_key", I), ("date", DT), ("year", I), ("month", I),
        ("iso_week", I), ("client_name", S), ("mission_key", I), ("mission_name", S), ("model_key", I),
        ("provider", S), ("model_name", S), ("config_label", S), ("type_code", S), ("section_code", S),
        ("section_title", S), ("status", S), ("sentences_total", I), ("sentences_verified", I),
        ("sentences_warning", I), ("sentences_failed", I), ("citations_total", I), ("citations_valid", I),
        ("numbers_cited", I), ("numbers_found", I), ("passages_retrieved", I), ("attempts", I),
        ("latency_ms", I), ("tokens_in", I), ("tokens_out", I), ("is_demo", I), ("tpv", D)],
    "v_quality_by_model": [
        ("model_key", I), ("provider", S), ("model_name", S), ("config_label", S), ("is_demo", I),
        ("n_generations", I), ("sentences_verified", I), ("sentences_total", I), ("tpv", D),
        ("citations_valid_rate", D), ("number_fidelity", D), ("refusal_rate", D), ("invalid_rate", D),
        ("avg_latency_ms", D)],
    "v_review_funnel": [
        ("deliverable_id", S), ("mission_key", I), ("type_key", I), ("is_demo", I),
        ("submitted_date_key", I), ("approved_date_key", I), ("rejections", I), ("submissions", I),
        ("delay_hours", D)],
    "v_outcome": [
        ("outcome_key", I), ("deliverable_id", S), ("approved_version", I), ("date_key", I),
        ("mission_key", I), ("section_code", S), ("section_title", S), ("config_label", S),
        ("generated_words", I), ("final_words", I), ("edit_ratio", D), ("unchanged", I), ("was_refused", I),
        ("minutes_saved_est", D), ("is_demo", I)],
    "v_citations": [
        ("citation_key", I), ("generation_key", I), ("issue_code", S), ("severity", S), ("document_key", I),
        ("document_mime", S), ("sentence_index", I), ("is_valid", I), ("support", D), ("is_demo", I)],
    "v_security": [
        ("mission_key", I), ("mission_name", S), ("document_key", I), ("document_id", S), ("mime", S),
        ("injection_alert_count", I), ("is_demo", I)],
    "v_llm_calls": [
        ("call_key", I), ("date_key", I), ("model_key", I), ("config_label", S), ("mission_key", I),
        ("call_kind", S), ("latency_ms", I), ("tokens_in", I), ("tokens_out", I), ("success", I),
        ("is_demo", I), ("tokens_per_second", D)],
}
BOOL_COLS = ["is_demo", "unchanged", "was_refused", "is_valid", "success"]
M_TYPE = {I: "Int64.Type", D: "type number", S: "type text", DT: "type date"}
HIDDEN_KEYS = {"generation_key", "model_key", "mission_key", "date_key", "citation_key", "call_key",
               "outcome_key", "document_key", "type_key", "submitted_date_key", "approved_date_key"}

# ---------------------------------------------------------------- mesures (nom, DAX, format)
PCT, DEC1, INT = "0.0%", "0.0", "#,0"
MEASURES: list[tuple[str, str, str]] = [
    ("TPV", "DIVIDE(SUM(v_generation[sentences_verified]), SUM(v_generation[sentences_total]))", PCT),
    ("Citations valides", "DIVIDE(SUM(v_generation[citations_valid]), SUM(v_generation[citations_total]))", PCT),
    ("Fidélité chiffres",
     "IF(SUM(v_generation[numbers_cited]) = 0, 1, DIVIDE(SUM(v_generation[numbers_found]), SUM(v_generation[numbers_cited])))", PCT),
    ("Taux refus",
     'DIVIDE(CALCULATE(COUNTROWS(v_generation), v_generation[status] = "refused"), COUNTROWS(v_generation))', PCT),
    ("Acceptation sans modif",
     "DIVIDE(CALCULATE(COUNTROWS(v_outcome), v_outcome[unchanged] = 1), COUNTROWS(v_outcome))", PCT),
    ("Temps gagné (h)", "SUM(v_outcome[minutes_saved_est]) / 60", DEC1),
    ("Latence p95 (s)", "PERCENTILEX.INC(v_llm_calls, v_llm_calls[latency_ms], 0.95) / 1000", DEC1),
    ("Δ TPV vs B",
     '[TPV] - CALCULATE([TPV], REMOVEFILTERS(Modèles[config_label]), Modèles[config_label] = "B")', "+0.0%;-0.0%;0.0%"),
    ("Livrables approuvés", "DISTINCTCOUNT(v_outcome[deliverable_id])", INT),
    ("Générations", "COUNTROWS(v_generation)", INT),
    ("Contrôles de citation", "COUNTROWS(v_citations)", INT),
    ("Réécriture moyenne", "AVERAGE(v_outcome[edit_ratio])", PCT),
    ("Délai médian (h)", "MEDIAN(v_review_funnel[delay_hours])", DEC1),
    ("Taux refus relecture", "DIVIDE(SUM(v_review_funnel[rejections]), SUM(v_review_funnel[submissions]))", PCT),
    ("Alertes d'injection", "SUM(v_security[injection_alert_count])", INT),
    ("Documents", "COUNTROWS(v_security)", INT),
    ("Livrables à l'étape",
     "SWITCH(SELECTEDVALUE(Etapes[Ordre]), "
     "1, DISTINCTCOUNT(v_review_funnel[deliverable_id]), "
     "2, CALCULATE(DISTINCTCOUNT(v_review_funnel[deliverable_id]), v_review_funnel[submissions] > 0), "
     "3, CALCULATE(DISTINCTCOUNT(v_review_funnel[deliverable_id]), v_review_funnel[approved_date_key] <> BLANK()))", INT),
]

# ---------------------------------------------------------------- relations (de, vers, active)
RELATIONS = [
    ("v_generation", "mission_key", "Missions", "mission_key", True),
    ("v_outcome", "mission_key", "Missions", "mission_key", True),
    ("v_review_funnel", "mission_key", "Missions", "mission_key", True),
    ("v_security", "mission_key", "Missions", "mission_key", True),
    ("v_llm_calls", "mission_key", "Missions", "mission_key", True),
    ("v_generation", "model_key", "Modèles", "model_key", True),
    ("v_llm_calls", "model_key", "Modèles", "model_key", True),
    ("v_quality_by_model", "model_key", "Modèles", "model_key", True),
    ("v_generation", "date_key", "Dates", "date_key", True),
    ("v_outcome", "date_key", "Dates", "date_key", True),
    ("v_llm_calls", "date_key", "Dates", "date_key", True),
    ("v_review_funnel", "submitted_date_key", "Dates", "date_key", False),
    ("v_citations", "generation_key", "v_generation", "generation_key", True),
]


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def j(path: Path, obj) -> None:
    w(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def q(name: str) -> str:
    """Nom TMDL : quotes simples si caractères spéciaux."""
    return f"'{name}'" if any(c in name for c in " ()'Δèé-") else name


# ================================================================ modèle sémantique
def column_tmdl(name: str, typ: str) -> str:
    out = f"\tcolumn {q(name)}\n\t\tdataType: {typ}\n"
    if typ == DT:
        out += "\t\tformatString: dd/mm/yyyy\n"
    out += f"\t\tsourceColumn: {name}\n\t\tsummarizeBy: none\n"
    if name in HIDDEN_KEYS:
        out = out.replace(f"\t\tdataType: {typ}\n", f"\t\tdataType: {typ}\n\t\tisHidden\n", 1)
    return out + "\n"


def vue_table(name: str, cols: list[tuple[str, str]]) -> str:
    types = ", ".join(f'{{"{c}", {M_TYPE[t]}}}' for c, t in cols)
    t = f"table {name}\n\n"
    t += "".join(column_tmdl(c, ty) for c, ty in cols)
    t += (f"\tpartition {name} = m\n\t\tmode: import\n\t\tsource =\n"
          f"\t\t\t\tlet\n\t\t\t\t    Brut = Vue(\"{name}\"),\n"
          f"\t\t\t\t    Typé = Table.TransformColumnTypes(Brut, {{{types}}}, CultureCsv)\n"
          f"\t\t\t\tin\n\t\t\t\t    Typé\n\n")
    return t


def lien_table(name: str, source: str, keys: list[tuple[str, str]], extra_m: str = "") -> str:
    cols = ", ".join(f'"{c}"' for c, _ in keys)
    t = f"table {q(name)}\n\n" + "".join(column_tmdl(c, ty) for c, ty in keys)
    t += (f"\tpartition {q(name)} = m\n\t\tmode: import\n\t\tsource =\n\t\t\t\tlet\n"
          f"\t\t\t\t    Base = Table.Distinct(Table.SelectColumns({source}, {{{cols}}})),\n"
          f"\t\t\t\t    Résultat = Table.Distinct(Base, {{\"{keys[0][0]}\"}}){extra_m}\n"
          f"\t\t\t\tin\n\t\t\t\t    Résultat\n\n")
    return t


def build_model() -> None:
    if SM.exists():
        shutil.rmtree(SM)
    j(SM / "definition.pbism", {"version": "4.2", "settings": {}})
    d = SM / "definition"
    w(d / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n")
    names = list(TABLES) + ["Missions", "Modèles", "Dates", "Etapes", "_Mesures"]
    w(d / "model.tmdl",
      "model Model\n\tculture: fr-FR\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n\n"
      + "".join(f"ref table {q(n)}\n" for n in names) + "\nref expression Source\nref expression DossierCsv\n"
      "ref expression CultureCsv\nref expression PgServer\nref expression PgDatabase\nref expression Vue\n")

    meta = 'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'
    w(d / "expressions.tmdl",
      f'expression Source = "CSV" {meta}\n\tlineageTag: src\n\n'
      f'expression DossierCsv = "{DEFAULT_CSV}" {meta}\n\n'
      f'expression CultureCsv = "fr-FR" {meta}\n\n'
      f'expression PgServer = "localhost:5432" {meta}\n\n'
      f'expression PgDatabase = "cadrage" {meta}\n\n'
      "expression Vue =\n"
      "\t\t(nom as text) as table =>\n"
      "\t\tlet\n"
      '\t\t    Brut = if Source = "CSV" then\n'
      '\t\t        Table.PromoteHeaders(Csv.Document(File.Contents(DossierCsv & "\\" & nom & ".csv"),\n'
      '\t\t            [Delimiter=";", Encoding=65001, QuoteStyle=QuoteStyle.None]), [PromoteAllScalars=true])\n'
      "\t\t    else\n"
      '\t\t        PostgreSQL.Database(PgServer, PgDatabase){[Schema="dw", Item=nom]}[Data],\n'
      f"\t\t    Booleens = List.Intersect({{Table.ColumnNames(Brut), {json.dumps(BOOL_COLS)}}}),\n"
      "\t\t    Numerique = Table.TransformColumns(Brut, List.Transform(Booleens, (c) => {c, (v) =>\n"
      "\t\t        if v is logical then (if v then 1 else 0) else v}))\n"
      "\t\tin\n\t\t    Numerique\n"
      "\t\tmeta [IsParameterQuery=false]\n")

    for name, cols in TABLES.items():
        w(d / "tables" / f"{name}.tmdl", vue_table(name, cols))

    # Missions : filtre client / mission / « Données » (démonstration ou réelles)
    w(d / "tables" / "Missions.tmdl",
      "table Missions\n\n"
      + "".join(column_tmdl(c, t) for c, t in [("mission_key", I), ("mission_name", S), ("client_name", S), ("is_demo", I)])
      + "\tcolumn Données\n\t\tdataType: string\n\t\tsourceColumn: Données\n\t\tsummarizeBy: none\n\n"
      "\tpartition Missions = m\n\t\tmode: import\n\t\tsource =\n\t\t\t\tlet\n"
      '\t\t\t\t    Base = Table.SelectColumns(v_generation, {"mission_key", "mission_name", "client_name", "is_demo"}),\n'
      '\t\t\t\t    Clé = Table.Distinct(Base, {"mission_key"}),\n'
      '\t\t\t\t    Libellé = Table.AddColumn(Clé, "Données", each if [is_demo] = 1 then "Démonstration" else "Réelles", type text)\n'
      "\t\t\t\tin\n\t\t\t\t    Libellé\n")

    w(d / "tables" / "Modèles.tmdl", lien_table(
        "Modèles", "v_generation",
        [("model_key", I), ("provider", S), ("model_name", S), ("config_label", S)]))

    w(d / "tables" / "Dates.tmdl",
      "table Dates\n\n"
      "\tcolumn Date\n\t\tdataType: dateTime\n\t\tformatString: dd/mm/yyyy\n\t\tsourceColumn: Date\n\t\tsummarizeBy: none\n\n"
      "\tcolumn date_key\n\t\tdataType: int64\n\t\tisHidden\n\t\tsourceColumn: date_key\n\t\tsummarizeBy: none\n\n"
      "\tcolumn Semaine\n\t\tdataType: dateTime\n\t\tformatString: dd/mm\n\t\tsourceColumn: Semaine\n\t\tsummarizeBy: none\n\n"
      "\tpartition Dates = m\n\t\tmode: import\n\t\tsource =\n\t\t\t\tlet\n"
      "\t\t\t\t    Liste = List.Dates(#date(2026, 1, 1), 730, #duration(1, 0, 0, 0)),\n"
      "\t\t\t\t    T = Table.FromList(Liste, Splitter.SplitByNothing(), {\"Date\"}, null, ExtraValues.Error),\n"
      "\t\t\t\t    Clé = Table.AddColumn(T, \"date_key\", each Date.Year([Date]) * 10000 + Date.Month([Date]) * 100 + Date.Day([Date]), Int64.Type),\n"
      "\t\t\t\t    Sem = Table.AddColumn(Clé, \"Semaine\", each Date.StartOfWeek([Date], Day.Monday), type date),\n"
      "\t\t\t\t    Types = Table.TransformColumnTypes(Sem, {{\"Date\", type date}})\n"
      "\t\t\t\tin\n\t\t\t\t    Types\n")

    w(d / "tables" / "Etapes.tmdl",
      "table Etapes\n\n"
      "\tcolumn Etape\n\t\tdataType: string\n\t\tsourceColumn: Etape\n\t\tsortByColumn: Ordre\n\t\tsummarizeBy: none\n\n"
      "\tcolumn Ordre\n\t\tdataType: int64\n\t\tsourceColumn: Ordre\n\t\tsummarizeBy: none\n\n"
      "\tpartition Etapes = calculated\n\t\tmode: import\n"
      "\t\tsource = DATATABLE(\"Etape\", STRING, \"Ordre\", INTEGER, {{\"Brouillon\", 1}, {\"En relecture\", 2}, {\"Approuvé\", 3}})\n")

    meas = ""
    for n, dax, fmt in MEASURES:
        meas += f"\tmeasure {q(n)} = {dax}\n\t\tformatString: {fmt}\n\n"
    w(d / "tables" / "_Mesures.tmdl",
      "table _Mesures\n\n\tcolumn Colonne\n\t\tdataType: string\n\t\tisHidden\n\t\tsourceColumn: Colonne\n\n"
      + meas + "\tpartition _Mesures = m\n\t\tmode: import\n\t\tsource = #table(type table [Colonne = text], {})\n")

    rel = ""
    for i, (ft, fc, tt, tc, active) in enumerate(RELATIONS, 1):
        rel += f"relationship r{i:02d}\n"
        if not active:
            rel += "\tisActive: false\n"
        rel += f"\tfromColumn: {q(ft)}.{q(fc)}\n\ttoColumn: {q(tt)}.{q(tc)}\n\n"
    w(d / "relationships.tmdl", rel)


# ================================================================ rapport PBIR
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


def col(entity: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def mes(prop: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Mesures"}}, "Property": prop}}


def proj(field: dict) -> dict:
    (kind, body), = field.items()
    ent = body["Expression"]["SourceRef"]["Entity"]
    p = body["Property"]
    return {"field": field, "queryRef": f"{ent}.{p}", "nativeQueryRef": p}


def lit(s: str) -> dict:
    return {"expr": {"Literal": {"Value": "'" + s.replace("'", "''") + "'"}}}


class Page:
    def __init__(self, pid: str, title: str, subtitle: str):
        self.id, self.title, self.n = pid, title, 0
        self.visuals: list[tuple[str, dict]] = []
        self.add_text(24, 14, 800, 40, title, "20pt", True)
        self.add_text(24, 52, 800, 24, subtitle, "11pt", False)
        self.add_text(840, 14, 416, 22, "Valeurs inventées — démonstration", "10pt", False)
        self.add("slicer", 840, 40, 416, 36, {"Values": [col("Missions", "Données")]},
                 mode="Basic")

    def add(self, vtype, x, y, w_, h, roles: dict, title: str | None = None, mode: str | None = None):
        self.n += 1
        name = f"{self.id}_v{self.n:02d}"
        visual: dict = {
            "visualType": vtype,
            "query": {"queryState": {r: {"projections": [proj(f) for f in fs]} for r, fs in roles.items()}},
            "drillFilterOtherVisuals": True,
        }
        if mode:
            visual["objects"] = {"data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Basic'"}}}}}]}
        obj: dict = {
            "$schema": f"{SCHEMA}/visualContainer/2.0.0/schema.json",
            "name": name,
            "position": {"x": x, "y": y, "width": w_, "height": h, "z": self.n, "tabOrder": self.n},
            "visual": visual,
        }
        if title:
            obj["visual"]["visualContainerObjects"] = {"title": [{"properties": {"text": lit(title)}}]}
        self.visuals.append((name, obj))

    def add_text(self, x, y, w_, h, text, size, bold):
        self.n += 1
        name = f"{self.id}_t{self.n:02d}"
        style = {"fontSize": size, "fontFamily": "Segoe UI Semibold" if bold else "Segoe UI",
                 "color": "#2E2E38" if bold else "#747480"}
        self.visuals.append((name, {
            "$schema": f"{SCHEMA}/visualContainer/2.0.0/schema.json",
            "name": name,
            "position": {"x": x, "y": y, "width": w_, "height": h, "z": self.n, "tabOrder": self.n},
            "visual": {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [
                {"textRuns": [{"value": text, "textStyle": style}]}]}}]}, "drillFilterOtherVisuals": True},
        }))

    def card(self, x, y, measure, label=None):
        self.add("card", x, y, 296, 96, {"Values": [mes(measure)]}, title=label)


def build_pages() -> list[Page]:
    pages: list[Page] = []

    p = Page("p1", "Vue d'ensemble", "Qualité, adoption et temps gagné")
    for i, m in enumerate(["TPV", "Acceptation sans modif", "Temps gagné (h)", "Livrables approuvés"]):
        p.card(24 + i * 312, 92, m)
    p.add("lineChart", 24, 204, 760, 492, {"Category": [col("Dates", "Semaine")], "Y": [mes("TPV")]},
          title="TPV par semaine")
    p.add("slicer", 800, 204, 456, 240, {"Values": [col("Missions", "client_name")]}, mode="Basic")
    p.add("slicer", 800, 456, 456, 240, {"Values": [col("v_generation", "type_code")]}, mode="Basic")
    pages.append(p)

    p = Page("p2", "Qualité et vérification", "Citations, chiffres, sections fragiles")
    p.add("barChart", 24, 92, 620, 604, {"Category": [col("v_citations", "issue_code")],
          "Y": [mes("Contrôles de citation")], "Series": [col("v_citations", "severity")]},
          title="Anomalies de citation par code")
    p.add("pivotTable", 660, 92, 596, 330, {"Rows": [col("v_generation", "section_title")],
          "Values": [mes("TPV")]}, title="TPV par section")
    p.add("clusteredColumnChart", 660, 438, 596, 258, {"Category": [col("v_generation", "type_code")],
          "Y": [mes("Fidélité chiffres")]}, title="Fidélité des chiffres par type")
    pages.append(p)

    p = Page("p3", "Comparaison des modèles", "Configurations A, B, C et D")
    p.add("clusteredColumnChart", 24, 92, 620, 360, {"Category": [col("Modèles", "config_label")],
          "Y": [mes("TPV"), mes("Citations valides"), mes("Taux refus")]}, title="Qualité par configuration")
    p.add("scatterChart", 660, 92, 596, 360, {"Category": [col("Modèles", "config_label")],
          "X": [mes("Latence p95 (s)")], "Y": [mes("TPV")], "Size": [mes("Générations")]},
          title="Latence p95 et TPV")
    p.add("tableEx", 24, 468, 1232, 228, {"Values": [col("Modèles", "config_label"), mes("TPV"),
          mes("Δ TPV vs B"), mes("Latence p95 (s)")]}, title="Écart au modèle B")
    pages.append(p)

    p = Page("p4", "Relecture", "Du brouillon à l'approbation")
    p.add("funnel", 24, 92, 620, 604, {"Category": [col("Etapes", "Etape")], "Y": [mes("Livrables à l'étape")]},
          title="Entonnoir de validation")
    p.card(660, 92, "Délai médian (h)")
    p.card(960, 92, "Taux refus relecture")
    p.add("barChart", 660, 204, 596, 492, {"Category": [col("v_outcome", "section_title")],
          "Y": [mes("Réécriture moyenne")]}, title="Sections les plus réécrites")
    pages.append(p)

    p = Page("p5", "Usage et sécurité", "Activité par mission, alertes d'injection")
    p.add("clusteredColumnChart", 24, 92, 760, 604, {"Category": [col("v_generation", "month")],
          "Y": [mes("Générations")], "Series": [col("Missions", "client_name")]},
          title="Générations par mois et par client")
    p.add("barChart", 800, 92, 456, 330, {"Category": [col("v_security", "mission_name")],
          "Y": [mes("Alertes d'injection")]}, title="Alertes d'injection par mission")
    p.add("donutChart", 800, 438, 456, 258, {"Category": [col("v_security", "mime")],
          "Y": [mes("Documents")]}, title="Documents par format")
    pages.append(p)
    return pages


def build_report() -> None:
    if RP.exists():
        shutil.rmtree(RP)
    j(RP / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../CadrageIA.SemanticModel"}},
    })
    d = RP / "definition"
    j(d / "version.json", {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    j(d / "report.json", {
        "$schema": f"{SCHEMA}/report/2.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU06", "reportVersionAtImport": "5.55", "type": "SharedResources"},
            "customTheme": {"name": "cadrage-ey.json", "reportVersionAtImport": "5.55", "type": "RegisteredResources"},
        },
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU06", "path": "BaseThemes/CY24SU06.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "cadrage-ey.json", "path": "cadrage-ey.json", "type": "CustomTheme"}]},
        ],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True},
    })
    res = RP / "StaticResources" / "RegisteredResources"
    res.mkdir(parents=True)
    shutil.copy(BI / "theme" / "cadrage-ey.json", res / "cadrage-ey.json")
    pages = build_pages()
    j(d / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.id for p in pages], "activePageName": pages[0].id})
    for p in pages:
        j(d / "pages" / p.id / "page.json", {
            "$schema": f"{SCHEMA}/page/2.0.0/schema.json", "name": p.id, "displayName": p.title,
            "displayOption": "FitToPage", "height": 720, "width": 1280})
        for name, obj in p.visuals:
            j(d / "pages" / p.id / "visuals" / name / "visual.json", obj)


def write_dax() -> None:
    out = ("// Mesures Power BI — GÉNÉRÉ par bi/pbip/build_pbip.py (ne pas éditer ici). 07 §5-6.\n"
           "// Sans PBIP : Accueil > Nouvelle mesure, une par bloc. Tables attendues : v_generation, v_outcome,\n"
           "// v_llm_calls, v_review_funnel, v_citations, v_security, Missions, Modèles, Dates, Etapes (bi/README.md §3).\n\n")
    for n, dax, fmt in MEASURES:
        out += f"{n} = {dax}\n\n"
    w(BI / "measures.dax", out)


if __name__ == "__main__":
    build_model()
    build_report()
    write_dax()
    w(ROOT / "CadrageIA.pbip", json.dumps(
        {"version": "1.0", "artifacts": [{"report": {"path": "CadrageIA.Report"}}],
         "settings": {"enableAutoRecovery": True}}, indent=2) + "\n")
    print("PBIP généré dans", ROOT)
