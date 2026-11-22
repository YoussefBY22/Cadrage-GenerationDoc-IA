"""Modèle sémantique TMDL : étoile en français au-dessus des vues de l'entrepôt (docs/07-entrepot-bi.md §4).

Les noms techniques des vues ne sont conservés que comme `sourceColumn` ; le rapport ne voit que les libellés.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from indicateurs import toutes

ENTIER, DECIMAL, TEXTE, DATE = "int64", "double", "string", "dateTime"
M_TYPE = {ENTIER: "Int64.Type", DECIMAL: "type number", TEXTE: "type text", DATE: "type date"}
BOOLEENS = ["is_demo", "unchanged", "was_refused", "is_valid", "success"]


@dataclass(frozen=True)
class Col:
    source: str
    nom: str
    type: str = TEXTE
    masquee: bool = True
    tri: str | None = None
    ajoutee: bool = False  # colonne créée dans Power Query, absente de la vue


def m_texte(valeur: str) -> str:
    return '"' + valeur.replace('"', '""') + '"'


def m_table(colonnes: list[tuple[str, str]], lignes: list[tuple]) -> str:
    entete = ", ".join(f'#"{nom}" = {t}' for nom, t in colonnes)
    corps = ", ".join("{" + ", ".join(m_texte(v) if isinstance(v, str) else str(v) for v in ligne) + "}"
                      for ligne in lignes)
    return f"#table(type table [{entete}], {{{corps}}})"


def m_libelles(paires: dict[str, str]) -> str:
    return "[" + ", ".join(f'#"{k}" = {m_texte(v)}' for k, v in paires.items()) + "]"


def q(nom: str) -> str:
    """Nom TMDL : apostrophes simples dès qu'il sort de [A-Za-z0-9_], apostrophe interne doublée."""
    simple = nom.isascii() and nom.replace("_", "").isalnum()
    return nom if simple else "'" + nom.replace("'", "''") + "'"


def ecrire(chemin: Path, texte: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8", newline="\n")


def colonne_tmdl(c: Col) -> str:
    out = [f"\tcolumn {q(c.nom)}", f"\t\tdataType: {c.type}"]
    if c.masquee:
        out.append("\t\tisHidden")
    if c.type == DATE:
        out.append("\t\tformatString: dd/mm/yyyy")
    out.append(f"\t\tsourceColumn: {c.source}")
    if c.tri:
        out.append(f"\t\tsortByColumn: {q(c.tri)}")
    out.append("\t\tsummarizeBy: none")
    return "\n".join(out) + "\n\n"


def table_tmdl(nom: str, cols: list[Col], etapes: list[tuple[str, str]], masquee: bool = False,
               mesures: str = "") -> str:
    out = f"table {q(nom)}\n" + ("\tisHidden\n" if masquee else "") + "\n"
    out += mesures + "".join(colonne_tmdl(c) for c in cols)
    corps = ",\n".join(f"\t\t\t\t    {k} = {v}" for k, v in etapes)
    out += (f"\tpartition {q(nom)} = m\n\t\tmode: import\n\t\tsource =\n"
            f"\t\t\t\tlet\n{corps}\n\t\t\t\tin\n\t\t\t\t    {etapes[-1][0]}\n")
    return out


def depuis_vue(vue: str, cols: list[Col]) -> list[tuple[str, str]]:
    """Étapes communes : lecture, sélection des colonnes utiles, typage selon la culture du CSV."""
    utiles = [c for c in cols if not c.ajoutee]
    noms = ", ".join(m_texte(c.source) for c in utiles)
    types = ", ".join(f"{{{m_texte(c.source)}, {M_TYPE[c.type]}}}" for c in utiles)
    return [("Brut", f'Vue("{vue}")'),
            ("Choix", f"Table.SelectColumns(Brut, {{{noms}}}, MissingField.UseNull)"),
            ("Typage", f"Table.TransformColumnTypes(Choix, {{{types}}}, CultureCsv)")]


def lu(vue: str, **types: str) -> str:
    """Lecture typée de quelques colonnes d'une vue.

    Chaque table lit la source elle-même : une requête qui référence une autre requête ET une source
    est bloquée par le pare-feu de confidentialité de Power Query (« Formula.Firewall »).
    """
    noms = ", ".join(map(m_texte, types))
    paires = ", ".join(f"{{{m_texte(c)}, {M_TYPE[t]}}}" for c, t in types.items())
    return f'Table.TransformColumnTypes(Table.SelectColumns(Vue("{vue}"), {{{noms}}}), {{{paires}}}, CultureCsv)'


# ---------------------------------------------------------------- libellés
ANOMALIES = {
    "NONE": "Aucune anomalie", "LOW_SUPPORT": "Preuve trop faible",
    "NUMBER_NOT_FOUND": "Chiffre introuvable", "FACT_WITHOUT_SOURCE": "Fait non sourcé",
    "UNKNOWN_SOURCE": "Source inexistante", "FOREIGN_SOURCE": "Source d'un autre dossier",
    "INSTRUCTION_ECHO": "Consigne recopiée", "UNKNOWN_FINDING": "Constat inexistant",
    "TRANSITION_WITH_NUMBER": "Chiffre dans une transition",
}
GRAVITES = {"blocking": "Bloquante", "warning": "À vérifier", "none": "Aucune"}
FORMATS = {
    "application/pdf": "PDF", "text/plain": "Texte",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint",
}
TYPES = [(1, "findings", "Constats"), (2, "roadmap", "Feuille de route"),
         (3, "tor", "Termes de référence"), (4, "cdc", "Cahier des charges")]
MOIS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août",
        "Septembre", "Octobre", "Novembre", "Décembre"]
MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
CONFIGURATION = ('each if [config_label] = null or [config_label] = "" '
                 'then "Non étiquetée" else [config_label], type text')


# ---------------------------------------------------------------- tables de faits
def tables_de_faits() -> dict[str, str]:
    t = {}

    cols = [
        Col("generation_key", "Clé de génération", ENTIER), Col("date_key", "Clé de date", ENTIER),
        Col("mission_key", "Clé de mission", ENTIER), Col("mission_name", "Mission d'origine"),
        Col("client_name", "Client d'origine"), Col("model_name", "Nom du modèle"),
        Col("config_label", "Code de configuration"), Col("config", "Clé de configuration", ajoutee=True),
        Col("type_code", "Code du type"), Col("nature", "Nature", ajoutee=True),
        Col("section_code", "Code de section"), Col("section", "Section", masquee=False, ajoutee=True),
        Col("section_title", "Titre de section d'origine"), Col("status", "Statut"),
        Col("sentences_total", "Phrases produites", ENTIER), Col("sentences_verified", "Phrases validées", ENTIER),
        Col("sentences_warning", "Phrases en avertissement", ENTIER),
        Col("sentences_failed", "Phrases en échec", ENTIER),
        Col("citations_total", "Citations produites", ENTIER),
        Col("citations_valid", "Citations valides en nombre", ENTIER),
        Col("numbers_cited", "Chiffres cités", ENTIER), Col("numbers_found", "Chiffres retrouvés", ENTIER),
        Col("is_demo", "Est une démonstration", ENTIER),
    ]
    t["Générations"] = table_tmdl("Générations", cols, depuis_vue("v_generation", cols) + [
        ("AvecConfiguration", f'Table.AddColumn(Typage, "config", {CONFIGURATION})'),
        ("AvecNature", 'Table.AddColumn(AvecConfiguration, "nature", '
                       'each if [type_code] = "findings" then "Constats" else "Section", type text)'),
        ("AvecSection", 'Table.AddColumn(AvecNature, "section", '
                        'each if [section_title] = "_all" then "Constats du dossier" else [section_title], type text)'),
    ])

    cols = [
        Col("deliverable_id", "Identifiant du livrable"), Col("date_key", "Clé de date", ENTIER),
        Col("mission_key", "Clé de mission", ENTIER), Col("config_label", "Code de configuration"),
        Col("config", "Clé de configuration", ajoutee=True), Col("type_key", "Clé de type", ENTIER, ajoutee=True),
        Col("section_title", "Section", masquee=False), Col("edit_ratio", "Part de texte modifiée", DECIMAL),
        Col("unchanged", "Sans retouche", ENTIER), Col("was_refused", "Refusée", ENTIER),
        Col("minutes_saved_est", "Minutes gagnées", DECIMAL),
        Col("baseline_minutes", "Minutes de référence", DECIMAL),
        Col("retouche", "Ampleur de la retouche", masquee=False, tri="Ordre de retouche", ajoutee=True),
        Col("retouche_ordre", "Ordre de retouche", ENTIER, ajoutee=True),
    ]
    ordre = ('each if [was_refused] = 1 then 5 else if [edit_ratio] = null or [edit_ratio] = 0 then 1 '
             'else if [edit_ratio] < 0.2 then 2 else if [edit_ratio] < 0.5 then 3 else 4, Int64.Type')
    t["Sections approuvées"] = table_tmdl("Sections approuvées", cols, depuis_vue("v_outcome", cols) + [
        # Un export antérieur à l'ajout de baseline_minutes reste lisible : l'ETL applique 30 min par section.
        ("AvecReference", 'Table.TransformColumns(Typage, '
                          '{{"baseline_minutes", each if _ = null then 30 else _, type number}})'),
        ("AvecConfiguration", f'Table.AddColumn(AvecReference, "config", {CONFIGURATION})'),
        ("TypeParLivrable", 'Table.TransformColumnTypes(Table.Distinct(Table.SelectColumns('
                            'Vue("v_review_funnel"), {"deliverable_id", "type_key"})), {{"type_key", Int64.Type}})'),
        ("Jointure", 'Table.NestedJoin(AvecConfiguration, {"deliverable_id"}, TypeParLivrable, '
                     '{"deliverable_id"}, "livrable", JoinKind.LeftOuter)'),
        ("AvecType", 'Table.ExpandTableColumn(Jointure, "livrable", {"type_key"})'),
        ("AvecOrdre", f'Table.AddColumn(AvecType, "retouche_ordre", {ordre})'),
        ("AvecRetouche", 'Table.AddColumn(AvecOrdre, "retouche", each {"Aucune", "Légère (< 20 %)", '
                         '"Moyenne (20–50 %)", "Forte (≥ 50 %)", "Section refusée"}'
                         '{[retouche_ordre] - 1}, type text)'),
    ])

    cols = [
        Col("deliverable_id", "Identifiant du livrable"), Col("mission_key", "Clé de mission", ENTIER),
        Col("type_key", "Clé de type", ENTIER), Col("approved_date_key", "Clé de date", ENTIER),
        Col("rejections", "Renvois", ENTIER), Col("submissions", "Soumissions", ENTIER),
        Col("delay_hours", "Délai en heures", DECIMAL),
    ]
    t["Relectures"] = table_tmdl("Relectures", cols, depuis_vue("v_review_funnel", cols), masquee=True)

    cols = [
        Col("generation_key", "Clé de génération", ENTIER), Col("issue_code", "Code de contrôle"),
        Col("anomalie", "Anomalie", masquee=False, ajoutee=True), Col("severity", "Code de gravité"),
        Col("gravite", "Gravité", masquee=False, ajoutee=True),
    ]
    t["Citations"] = table_tmdl("Citations", cols, depuis_vue("v_citations", cols) + [
        ("AvecAnomalie", f'Table.AddColumn(Typage, "anomalie", each Record.FieldOrDefault('
                         f'{m_libelles(ANOMALIES)}, [issue_code], "Autre anomalie"), type text)'),
        ("AvecGravite", f'Table.AddColumn(AvecAnomalie, "gravite", each Record.FieldOrDefault('
                        f'{m_libelles(GRAVITES)}, [severity], "Autre"), type text)'),
    ])

    cols = [
        Col("mission_key", "Clé de mission", ENTIER), Col("document_key", "Clé de document", ENTIER),
        Col("mime", "Code de format"), Col("format", "Format", masquee=False, ajoutee=True),
        Col("injection_alert_count", "Alertes", ENTIER), Col("date_key", "Clé de date", ENTIER, ajoutee=True),
    ]
    t["Documents"] = table_tmdl("Documents", cols, depuis_vue("v_security", cols) + [
        ("AvecFormat", f'Table.AddColumn(Typage, "format", each Record.FieldOrDefault('
                       f'{m_libelles(FORMATS)}, [mime], "Autre"), type text)'),
        # La vue ne date pas les documents : ils prennent la date de la première génération de leur mission.
        ("Generations", lu("v_generation", mission_key=ENTIER, date_key=ENTIER)),
        ("DateParMission", 'Table.Group(Generations, {"mission_key"}, '
                           '{{"date_key", each List.Min([date_key]), Int64.Type}})'),
        ("Jointure", 'Table.NestedJoin(AvecFormat, {"mission_key"}, DateParMission, '
                     '{"mission_key"}, "mission", JoinKind.LeftOuter)'),
        ("AvecDate", 'Table.ExpandTableColumn(Jointure, "mission", {"date_key"})'),
    ])

    cols = [
        Col("date_key", "Clé de date", ENTIER), Col("mission_key", "Clé de mission", ENTIER),
        Col("config_label", "Code de configuration"), Col("config", "Clé de configuration", ajoutee=True),
        Col("call_kind", "Nature"), Col("latency_ms", "Latence en ms", ENTIER),
    ]
    t["Appels au modèle"] = table_tmdl("Appels au modèle", cols, depuis_vue("v_llm_calls", cols) + [
        ("AvecConfiguration", f'Table.AddColumn(Typage, "config", {CONFIGURATION})'),
    ], masquee=True)
    return t


# ---------------------------------------------------------------- dimensions
def dimensions() -> dict[str, str]:
    t = {}

    t["Missions"] = table_tmdl("Missions", [
        Col("mission_key", "Clé de mission", ENTIER), Col("mission_name", "Mission", masquee=False),
        Col("client_name", "Client", masquee=False), Col("is_demo", "Est une démonstration", ENTIER),
    ], [
        ("Actives", lu("v_generation", mission_key=ENTIER, mission_name=TEXTE, client_name=TEXTE, is_demo=ENTIER)),
        ("Importees", lu("v_security", mission_key=ENTIER, mission_name=TEXTE, is_demo=ENTIER)),
        ("SansGeneration", 'Table.AddColumn(Table.SelectRows(Importees, each not List.Contains('
                           'Actives[mission_key], [mission_key])), "client_name", each "Non renseigné", type text)'),
        ("Resultat", 'Table.Distinct(Table.Combine({Actives, SansGeneration}), {"mission_key"})'),
    ])

    t["Configurations"] = table_tmdl("Configurations", [
        Col("config", "Configuration", masquee=False),
        Col("libelle", "Configuration et modèle", masquee=False, tri="Configuration"),
    ], [
        ("Paires", f'Table.AddColumn({lu("v_generation", config_label=TEXTE, model_name=TEXTE)}, "config", {CONFIGURATION})'),
        ("Groupes", 'Table.Group(Paires, {"config"}, {{"libelle", each [config]{0} & " · " & '
                    'Text.Combine(List.Distinct(List.Transform([model_name], Text.From)), ", "), type text}})'),
    ])

    types = m_table([("type_key", "Int64.Type"), ("type_code", "text"), ("libelle", "text")], TYPES)
    t["Types de livrable"] = table_tmdl("Types de livrable", [
        Col("type_key", "Clé de type", ENTIER), Col("type_code", "Code du type"),
        Col("libelle", "Type de livrable", masquee=False, tri="Clé de type"),
    ], [
        ("Tous", types),
        ("Utilises", f'List.Buffer(List.Distinct(Table.Column({lu("v_generation", type_code=TEXTE)}, "type_code")))'),
        ("Presents", 'Table.SelectRows(Tous, each List.Contains(Utilises, [type_code]))'),
    ])

    mois = "{" + ", ".join(map(m_texte, MOIS)) + "}"
    courts = "{" + ", ".join(map(m_texte, MOIS_COURTS)) + "}"
    t["Calendrier"] = table_tmdl("Calendrier", [
        Col("jour", "Date", DATE, masquee=False), Col("date_key", "Clé de date", ENTIER),
        Col("mois_ordre", "Ordre du mois", ENTIER),
        Col("mois", "Mois", masquee=False, tri="Ordre du mois"),
        Col("mois_court", "Mois abrégé", masquee=False, tri="Ordre du mois"),
    ], [
        # Le calendrier ne couvre que les mois présents dans les données : le segment reste court.
        ("Cles", f'List.RemoveNulls(List.Combine({{Table.Column({lu("v_generation", date_key=ENTIER)}, "date_key"), '
                 f'Table.Column({lu("v_outcome", date_key=ENTIER)}, "date_key")}}))'),
        ("VersDate", "(k as number) as date => #date(Number.IntegerDivide(k, 10000), "
                     "Number.Mod(Number.IntegerDivide(k, 100), 100), Number.Mod(k, 100))"),
        ("Debut", "Date.StartOfMonth(VersDate(List.Min(Cles, 20260101)))"),
        ("Fin", "Date.EndOfMonth(VersDate(List.Max(Cles, 20261231)))"),
        ("Jours", "List.Dates(Debut, Duration.Days(Fin - Debut) + 1, #duration(1, 0, 0, 0))"),
        ("Base", 'Table.FromColumns({Jours}, type table [jour = date])'),
        ("AvecCle", 'Table.AddColumn(Base, "date_key", '
                    "each Date.Year([jour]) * 10000 + Date.Month([jour]) * 100 + Date.Day([jour]), Int64.Type)"),
        ("AvecOrdre", 'Table.AddColumn(AvecCle, "mois_ordre", '
                      "each Date.Year([jour]) * 100 + Date.Month([jour]), Int64.Type)"),
        ("AvecMois", f'Table.AddColumn(AvecOrdre, "mois", each {mois}{{Date.Month([jour]) - 1}} '
                     '& " " & Text.From(Date.Year([jour])), type text)'),
        # Le millésime distingue deux mêmes mois d'années différentes (le tri exige une relation 1:1).
        ("AvecMoisCourt", f'Table.AddColumn(AvecMois, "mois_court", each {courts}{{Date.Month([jour]) - 1}} '
                          '& " " & Text.End(Text.From(Date.Year([jour])), 2), type text)'),
    ])

    # Tables déconnectées qui portent les axes de la cascade, de l'entonnoir et des petits multiples.
    for nom, colonne, valeurs in (
        ("Cascade", "Résultat du contrôle", ["Générées", "À vérifier", "Rejetées"]),
        ("Étapes", "Étape", ["Demandées", "Rédigées", "Approuvées", "Sans retouche"]),
        ("Critères", "Critère", ["Phrases vérifiées", "Citations valides", "Chiffres retrouvés",
                                 "Acceptées sans retouche"]),
    ):
        contenu = m_table([("libelle", "text"), ("ordre", "Int64.Type")],
                          [(v, i) for i, v in enumerate(valeurs, 1)])
        t[nom] = table_tmdl(nom, [Col("libelle", colonne, masquee=False, tri="Ordre"),
                                  Col("ordre", "Ordre", ENTIER)], [("Resultat", contenu)], masquee=True)
    return t


def indicateurs_tmdl() -> str:
    blocs = ""
    for m in toutes():
        blocs += "".join(f"\t/// {ligne}\n" for ligne in m.description.split("\n") if ligne)
        if "\n" in m.dax:
            blocs += f"\tmeasure {q(m.nom)} =\n" + "".join(f"\t\t\t{ligne}\n" for ligne in m.dax.split("\n"))
        else:
            blocs += f"\tmeasure {q(m.nom)} = {m.dax}\n"
        if m.fmt:
            blocs += f"\t\tformatString: {m.fmt}\n"
        blocs += f"\t\tdisplayFolder: {m.dossier}\n"
        if m.masquee:
            blocs += "\t\tisHidden\n"
        blocs += "\n"
    return table_tmdl("Indicateurs", [Col("Colonne", "Colonne")],
                      [("Vide", "#table(type table [Colonne = text], {})")], mesures=blocs)


RELATIONS = [
    ("Générations", "Clé de mission", "Missions", "Clé de mission"),
    ("Sections approuvées", "Clé de mission", "Missions", "Clé de mission"),
    ("Relectures", "Clé de mission", "Missions", "Clé de mission"),
    ("Documents", "Clé de mission", "Missions", "Clé de mission"),
    ("Appels au modèle", "Clé de mission", "Missions", "Clé de mission"),
    ("Générations", "Clé de date", "Calendrier", "Clé de date"),
    ("Sections approuvées", "Clé de date", "Calendrier", "Clé de date"),
    ("Relectures", "Clé de date", "Calendrier", "Clé de date"),
    ("Documents", "Clé de date", "Calendrier", "Clé de date"),
    ("Appels au modèle", "Clé de date", "Calendrier", "Clé de date"),
    ("Générations", "Clé de configuration", "Configurations", "Configuration"),
    ("Sections approuvées", "Clé de configuration", "Configurations", "Configuration"),
    ("Appels au modèle", "Clé de configuration", "Configurations", "Configuration"),
    ("Générations", "Code du type", "Types de livrable", "Code du type"),
    ("Sections approuvées", "Clé de type", "Types de livrable", "Clé de type"),
    ("Relectures", "Clé de type", "Types de livrable", "Clé de type"),
    ("Citations", "Clé de génération", "Générations", "Clé de génération"),
]


def expressions(dossier_csv: str) -> str:
    meta = 'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'
    parametres = {"Source": "CSV", "DossierCsv": dossier_csv, "CultureCsv": "fr-FR",
                  "PgServer": "localhost:5432", "PgDatabase": "cadrage"}
    out = "".join(f"expression {k} = {m_texte(v)} {meta}\n\n" for k, v in parametres.items())
    booleens = "{" + ", ".join(json.dumps(b) for b in BOOLEENS) + "}"
    return out + (
        "expression Vue =\n"
        "\t\t(nom as text) as table =>\n"
        "\t\tlet\n"
        '\t\t    Separateur = if Text.StartsWith(CultureCsv, "fr") then ";" else ",",\n'
        '\t\t    Brut = if Source = "CSV" then\n'
        '\t\t        Table.PromoteHeaders(Csv.Document(File.Contents(DossierCsv & "\\" & nom & ".csv"),\n'
        "\t\t            [Delimiter=Separateur, Encoding=65001, QuoteStyle=QuoteStyle.Csv]), [PromoteAllScalars=true])\n"
        "\t\t    else\n"
        '\t\t        PostgreSQL.Database(PgServer, PgDatabase){[Schema="dw", Item=nom]}[Data],\n'
        f"\t\t    Booleens = List.Intersect({{Table.ColumnNames(Brut), {booleens}}}),\n"
        "\t\t    Numerique = Table.TransformColumns(Brut, List.Transform(Booleens, (c) => {c, (v) =>\n"
        '\t\t        if v = true or v = "true" then 1 else if v = false or v = "false" then 0 else v}))\n'
        "\t\tin\n"
        "\t\t    Numerique\n")


def construire_modele(racine: Path, dossier_csv: str) -> None:
    ecrire(racine / "definition.pbism", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2) + "\n")
    ecrire(racine / ".pbi" / "editorSettings.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/editorSettings/1.0.0/schema.json",
        # Le chargement parallèle fait échouer par intermittence la première actualisation
        # (« A cyclic reference was encountered during evaluation ») : requêtes chargées l'une après l'autre.
        "parallelQueryLoading": False,
        # Relations et types sont déclarés dans le TMDL : rien à deviner.
        "autodetectRelationships": False,
        "typeDetectionEnabled": False,
        "relationshipImportEnabled": False,
        "shouldNotifyUserOfNameConflictResolution": True,
    }, indent=2) + "\n")
    d = racine / "definition"
    tables = {"Indicateurs": indicateurs_tmdl(), **dimensions(), **tables_de_faits()}
    ecrire(d / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n")
    ecrire(d / "model.tmdl",
           "model Model\n\tculture: fr-FR\n\tsourceQueryCulture: fr-FR\n"
           "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n\n"
           "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
           + "".join(f"ref table {q(n)}\n" for n in tables) + "\n"
           + "".join(f"ref expression {n}\n" for n in
                     ("Source", "DossierCsv", "CultureCsv", "PgServer", "PgDatabase", "Vue")))
    ecrire(d / "expressions.tmdl", expressions(dossier_csv))
    for nom, texte in tables.items():
        ecrire(d / "tables" / f"{nom}.tmdl", texte)
    ecrire(d / "relationships.tmdl", "".join(
        f"relationship r{i:02d}\n\tfromColumn: {q(a)}.{q(b)}\n\ttoColumn: {q(c)}.{q(e)}\n\n"
        for i, (a, b, c, e) in enumerate(RELATIONS, 1)))
