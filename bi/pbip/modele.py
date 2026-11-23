"""Modèle sémantique TMDL : étoile en français au-dessus des vues de l'entrepôt (docs/07 §4).

Les noms techniques des vues ne sont conservés que comme `sourceColumn` ; le rapport ne voit que les libellés.
Chaque segment porte une vraie valeur « Tous » (table de choix reliée en plusieurs-à-plusieurs) : le libellé
ne dépend donc pas de la langue de Power BI Desktop, et la prédiction sait quel périmètre lire.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from indicateurs import TOUS, TOUT, pilotage, toutes

ENTIER, DECIMAL, TEXTE, DATE = "int64", "double", "string", "dateTime"
M_TYPE = {ENTIER: "Int64.Type", DECIMAL: "type number", TEXTE: "type text", DATE: "type date"}
BOOLEENS = ["is_demo", "unchanged", "was_refused", "returned", "refused", "first_rejected",
            "has_retrieval", "simulated"]


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


def m_libelle(colonne: str, paires: dict[str, str], defaut: str) -> str:
    return (f"each if [{colonne}] = null then {m_texte(defaut)} else "
            f"Record.FieldOrDefault({m_libelles(paires)}, [{colonne}], {m_texte(defaut)}), type text")


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
        # Jour et mois en chiffres : les noms de mois suivraient la langue de Power BI Desktop
        out.append("\t\tformatString: " + ("dd/MM" if c.source == "period_end" else "dd/MM/yyyy"))
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
            ("Choix", f"Table.SelectColumns(Brut, {{{noms}}})"),
            ("Typage", f"Table.TransformColumnTypes(Choix, {{{types}}}, CultureCsv)")]


def lu(vue: str, **types: str) -> str:
    """Lecture typée de quelques colonnes d'une vue.

    Chaque table lit la source elle-même : une requête qui référence une autre requête ET une source
    est bloquée par le pare-feu de confidentialité de Power Query (« Formula.Firewall »).
    """
    noms = ", ".join(map(m_texte, types))
    paires = ", ".join(f"{{{m_texte(c)}, {M_TYPE[t]}}}" for c, t in types.items())
    return f'Table.TransformColumnTypes(Table.SelectColumns(Vue("{vue}"), {{{noms}}}), {{{paires}}}, CultureCsv)'


def colonne_lue(vue: str, colonne: str, typ: str) -> str:
    return f'Table.Column({lu(vue, **{colonne: typ})}, "{colonne}")'


# ---------------------------------------------------------------- libellés
FORMATS = {
    "application/pdf": "PDF", "text/plain": "Texte", "text/markdown": "Markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint",
}
TYPES = [(1, "findings", "Constats"), (2, "roadmap", "Feuille de route"),
         (3, "tor", "Termes de référence"), (4, "cdc", "Cahier des charges")]
TYPES_COURTS = {"1": "constats", "2": "feuille de route", "3": "TdR", "4": "CdC"}
ETATS = {"draft": "Brouillon", "in_review": "En relecture", "approved": "Approuvé", "rejected": "Renvoyé"}
DECISIONS = {"reference": "Référence", "retain": "À retenir", "inconclusive": "Non concluant",
             "unsafe": "Rejetée : sécurité dégradée", "worse": "Moins bonne", "not_paired": "Non comparable"}
MONTAGES = {"A": "Sans recherche", "B": "Référence", "C": "B + LoRA", "D": "Autre taille de modèle"}
MOIS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août",
        "Septembre", "Octobre", "Novembre", "Décembre"]
VERS_DATE = ("(k as number) as date => #date(Number.IntegerDivide(k, 10000), "
             "Number.Mod(Number.IntegerDivide(k, 100), 100), Number.Mod(k, 100))")
CLE_DU_JOUR = "Date.Year([jour]) * 10000 + Date.Month([jour]) * 100 + Date.Day([jour])"


def types_m() -> str:
    return m_table([("type_key", "Int64.Type"), ("type_code", "text"), ("libelle", "text")], TYPES)


# ---------------------------------------------------------------- tables de faits
def tables_de_faits() -> dict[str, str]:
    t = {}

    cols = [
        Col("date_key", "Clé de date", ENTIER), Col("mission_key", "Clé de mission", ENTIER),
        Col("author_key", "Clé de consultant", ENTIER), Col("type_code", "Code du type"),
        Col("status", "Statut"), Col("sentences_total", "Phrases produites", ENTIER),
        Col("sentences_verified", "Phrases validées", ENTIER),
        Col("citations_total", "Citations produites", ENTIER),
        Col("citations_valid", "Citations valides en nombre", ENTIER),
    ]
    t["Générations"] = table_tmdl("Générations", cols, depuis_vue("v_generation", cols), masquee=True)

    cols = [
        Col("date_key", "Clé de date", ENTIER), Col("mission_key", "Clé de mission", ENTIER),
        Col("type_key", "Clé de type", ENTIER), Col("author_key", "Clé de consultant", ENTIER),
        Col("unchanged", "Sans retouche", ENTIER), Col("was_refused", "Refusée", ENTIER),
    ]
    t["Sections approuvées"] = table_tmdl("Sections approuvées", cols, depuis_vue("v_outcome", cols), masquee=True)

    cols = [
        Col("deliverable_id", "Identifiant du livrable"), Col("mission_key", "Clé de mission", ENTIER),
        Col("mission_name", "Mission d'origine"), Col("type_key", "Clé de type", ENTIER),
        Col("author_key", "Clé de consultant", ENTIER), Col("reviewer_key", "Clé de responsable", ENTIER),
        Col("dossier", "Livrable", masquee=False, ajoutee=True),
        Col("state", "Code d'état"), Col("etat", "État", masquee=False, ajoutee=True),
        Col("approved_date_key", "Clé d'approbation", ENTIER),
        Col("submitted_date_key", "Clé de soumission", ENTIER),
        Col("as_of", "Date de situation"), Col("state_age_hours", "Heures dans l'état", DECIMAL),
        Col("idle_hours", "Heures sans activité", DECIMAL), Col("returned", "Renvoyé", ENTIER),
        Col("reason_code", "Code du motif"), Col("motif", "Motif du renvoi", masquee=False, ajoutee=True),
        Col("refused_sections", "Sections sans preuve", ENTIER),
        Col("blocking_open", "Phrases bloquantes", ENTIER),
        Col("citations_total", "Citations finales", ENTIER),
        Col("citations_invalid", "Citations sans source", ENTIER),
        Col("delay_hours", "Délai en heures", DECIMAL),
        Col("first_rejected", "Renvoyé en première relecture", ENTIER),
        Col("risk", "Risque", DECIMAL), Col("risk_low", "Risque bas", DECIMAL),
        Col("risk_high", "Risque haut", DECIMAL), Col("risk_n", "Risque effectif", ENTIER),
        Col("is_demo", "Est une démonstration", ENTIER),
    ]
    motifs = {code: libelle for code, libelle, _ in pilotage.REASONS}
    t["Livrables"] = table_tmdl("Livrables", cols, depuis_vue("v_deliverable", cols) + [
        ("AvecNom", 'Table.AddColumn(Typage, "dossier", each [mission_name] & " · " & '
                    f'Record.FieldOrDefault({m_libelles(TYPES_COURTS)}, Text.From([type_key]), "autre"), type text)'),
        ("AvecEtat", f'Table.AddColumn(AvecNom, "etat", {m_libelle("state", ETATS, "Inconnu")})'),
        ("AvecMotif", f'Table.AddColumn(AvecEtat, "motif", {m_libelle("reason_code", motifs, "—")})'),
    ])

    cols = [
        Col("deliverable_id", "Identifiant du livrable"),
        Col("section_title", "Section", masquee=False),
        Col("blocking", "Bloquantes", ENTIER), Col("citations_invalid", "Sans source", ENTIER),
        Col("refused", "Refus", ENTIER), Col("priority", "Priorité de section", ENTIER),
        Col("libelle", "Section à revoir", masquee=False, ajoutee=True),
    ]
    t["Sections courantes"] = table_tmdl("Sections courantes", cols, depuis_vue("v_section_current", cols) + [
        ("Livres", lu("v_deliverable", deliverable_id=TEXTE, mission_name=TEXTE)),
        ("Jointure", 'Table.NestedJoin(Typage, {"deliverable_id"}, Livres, {"deliverable_id"}, "l", JoinKind.LeftOuter)'),
        ("AvecMission", 'Table.ExpandTableColumn(Jointure, "l", {"mission_name"})'),
        ("AvecLibelle", 'Table.AddColumn(AvecMission, "libelle", each [section_title] & " · " & [mission_name], type text)'),
        ("Utiles", 'Table.RemoveColumns(AvecLibelle, {"mission_name"})'),
    ])

    cols = [Col("deliverable_id", "Identifiant du livrable"), Col("rule_code", "Code de règle signalée")]
    t["Actions"] = table_tmdl("Actions", cols, depuis_vue("v_action", cols), masquee=True)

    cols = [
        Col("forecast_key", "Clé de prévision", ENTIER), Col("client_name", "Client prévu"),
        Col("type_key", "Clé de type prévu", ENTIER), Col("author_key", "Clé de personne prévue", ENTIER),
        Col("reviewer_key", "Clé de responsable prévu", ENTIER),
        Col("rang", "Rang de périmètre", ENTIER, ajoutee=True),
        Col("status", "Statut de prévision"), Col("weeks", "Semaines", ENTIER),
        Col("events", "Soumissions", ENTIER), Col("origins", "Origines", ENTIER),
        Col("point", "Point", DECIMAL), Col("low", "Bas", DECIMAL), Col("high", "Haut", DECIMAL),
        Col("mae", "Erreur", DECIMAL), Col("mae_naive", "Erreur naïve", DECIMAL),
        Col("risk_status", "Statut du risque"), Col("risk_brier", "Brier", DECIMAL),
        Col("risk_brier_naive", "Brier naïf", DECIMAL), Col("risk_tested", "Cas testés", ENTIER),
        Col("perimetre_client", "Périmètre client", ajoutee=True),
        Col("perimetre_type", "Périmètre type", ajoutee=True),
        Col("perimetre_consultant", "Périmètre consultant", ajoutee=True),
    ]
    types = m_libelles({str(k): libelle for k, _, libelle in TYPES})
    t["Prévisions"] = table_tmdl("Prévisions", cols, depuis_vue("v_forecast", cols) + [
        ("AvecClient", 'Table.AddColumn(Typage, "perimetre_client", each if [client_name] = null or [client_name] = "" '
                       f'then {m_texte(TOUS)} else [client_name], type text)'),
        ("AvecType", 'Table.AddColumn(AvecClient, "perimetre_type", each if [type_key] = null '
                     f'then {m_texte(TOUS)} else Record.FieldOrDefault({types}, Text.From([type_key]), "Autre"), type text)'),
        ("Gens", lu("v_person", user_key=ENTIER, user_label=TEXTE)),
        ("Jointure", 'Table.NestedJoin(AvecType, {"author_key"}, Gens, {"user_key"}, "p", JoinKind.LeftOuter)'),
        ("AvecNom", 'Table.ExpandTableColumn(Jointure, "p", {"user_label"})'),
        ("AvecRang", 'Table.AddColumn(AvecNom, "rang", each (if [author_key] = null then 0 else 1) '
                     '+ (if [reviewer_key] = null then 0 else 2), Int64.Type)'),
        ("AvecPersonne", 'Table.AddColumn(AvecRang, "perimetre_consultant", each if [author_key] = null '
                         f'then {m_texte(TOUS)} else [user_label], type text)'),
        ("Utiles", 'Table.RemoveColumns(AvecPersonne, {"user_label"})'),
    ], masquee=True)

    cols = [
        Col("forecast_key", "Clé de prévision", ENTIER),
        Col("period_end", "Fin de quinzaine", DATE, masquee=False),
        Col("actual", "Réel", ENTIER), Col("point", "Point prévu", DECIMAL),
        Col("low", "Borne basse prévue", DECIMAL), Col("high", "Borne haute prévue", DECIMAL),
    ]
    t["Série de prévision"] = table_tmdl("Série de prévision", cols, depuis_vue("v_forecast_point", cols))

    cols = [Col("as_of", "Date de situation", ajoutee=True), Col("is_demo", "Est une démonstration", ENTIER, ajoutee=True)]
    # Une ligne, hors RLS : date et nature des données, qui doivent rester visibles pour tous les rôles.
    t["Source des données"] = table_tmdl("Source des données", cols, [
        ("Tous", lu("v_deliverable", as_of=TEXTE, is_demo=ENTIER)),
        ("Resultat", '#table(type table [as_of = text, is_demo = Int64.Type], '
                     '{{List.Max(Tous[as_of]), List.Max(Tous[is_demo], 0)}})'),
    ], masquee=True)

    cols = [
        Col("config_label", "Configuration", masquee=False), Col("model_name", "Modèle du banc"),
        Col("adapter", "Adaptation"), Col("has_retrieval", "Avec recherche", ENTIER),
        Col("montage", "Montage", ajoutee=True),
        Col("n_sections", "Sections du banc", ENTIER), Col("tpv", "TPV", DECIMAL),
        Col("tpv_low", "TPV bas", DECIMAL), Col("tpv_high", "TPV haut", DECIMAL),
        Col("delta", "Écart", DECIMAL), Col("delta_low", "Écart bas", DECIMAL),
        Col("delta_high", "Écart haut", DECIMAL), Col("decision", "Code de décision"),
        Col("verdict", "Décision", ajoutee=True),
        Col("citation_validity", "Citations valides", DECIMAL), Col("number_fidelity", "Chiffres fidèles", DECIMAL),
        Col("attack_success", "Attaques réussies", DECIMAL), Col("latency_p95_ms", "Latence p95", DECIMAL),
        Col("simulated", "Simulé", ENTIER),
    ]
    t["Banc"] = table_tmdl("Banc", cols, depuis_vue("v_bench", cols) + [
        # Un résultat simulé n'est pas une mesure ; le protocole reste lisible sans résultat.
        ("Mesures", "Table.Buffer(Table.SelectRows(Typage, each [simulated] <> 1))"),
        ("Absentes", "Table.SelectRows(" + m_table([("config_label", "text")], [(k,) for k in MONTAGES])
                     + ', each not List.Contains(Table.Column(Mesures, "config_label"), [config_label]))'),
        ("Completees", "Table.Combine({Mesures, Absentes})"),
        ("AvecMontage", 'Table.AddColumn(Completees, "montage", each if [model_name] = null '
                        f'then Record.FieldOrDefault({m_libelles(MONTAGES)}, [config_label], "") else [model_name] & '
                        '(if [adapter] = null or [adapter] = "" then "" else " + LoRA") & '
                        '(if [has_retrieval] = 1 then "" else ", sans recherche"), type text)'),
        ("AvecVerdict", f'Table.AddColumn(AvecMontage, "verdict", {m_libelle("decision", DECISIONS, "Non mesuré")})'),
    ])

    cols = [
        Col("mission_key", "Clé de mission", ENTIER), Col("mime", "Code de format"),
        Col("format", "Format", masquee=False, ajoutee=True), Col("injection_alert_count", "Alertes", ENTIER),
    ]
    t["Documents"] = table_tmdl("Documents", cols, depuis_vue("v_security", cols) + [
        ("AvecFormat", f'Table.AddColumn(Typage, "format", {m_libelle("mime", FORMATS, "Autre")})'),
    ])
    return t


# ---------------------------------------------------------------- dimensions et choix
def choix(nom: str, libelle: str, tous: str, valeurs: str) -> str:
    """Table de segment : la valeur « Tous » pointe vers chaque membre, chaque membre vers lui-même."""
    return table_tmdl(nom, [
        Col("choix", libelle, masquee=False, tri="Rang"), Col("cible", "Cible"), Col("rang", "Rang", ENTIER),
    ], [
        ("Valeurs", f"List.Buffer(List.Sort(List.Distinct(List.RemoveNulls({valeurs}))))"),
        ("Toutes", f"List.Transform(Valeurs, each {{{m_texte(tous)}, _, 0}})"),
        ("Chacune", "List.Transform(Valeurs, each {_, _, List.PositionOf(Valeurs, _) + 1})"),
        ("Resultat", '#table(type table [choix = text, cible = text, rang = Int64.Type], Toutes & Chacune)'),
    ])


def dimensions() -> dict[str, str]:
    t = {}

    t["Missions"] = table_tmdl("Missions", [
        Col("mission_key", "Clé de mission", ENTIER), Col("mission_name", "Mission", masquee=False),
        Col("client_name", "Client", masquee=False),
    ], [
        ("Suivies", lu("v_deliverable", mission_key=ENTIER, mission_name=TEXTE, client_name=TEXTE)),
        ("Actives", lu("v_generation", mission_key=ENTIER, mission_name=TEXTE, client_name=TEXTE)),
        ("Importees", lu("v_security", mission_key=ENTIER, mission_name=TEXTE)),
        ("SansClient", 'Table.AddColumn(Importees, "client_name", each "Non renseigné", type text)'),
        # Table.Buffer fige l'ordre : le client connu l'emporte sur « Non renseigné »
        ("Resultat", 'Table.Distinct(Table.Buffer(Table.Combine({Suivies, Actives, SansClient})), {"mission_key"})'),
    ])

    t["Types de livrable"] = table_tmdl("Types de livrable", [
        Col("type_key", "Clé de type", ENTIER), Col("type_code", "Code du type"),
        Col("libelle", "Type de livrable", masquee=False, tri="Clé de type"),
    ], [("Resultat", types_m())])

    t["Personnes"] = table_tmdl("Personnes", [
        Col("user_key", "Clé de personne", ENTIER), Col("user_label", "Consultant", masquee=False),
    ], [
        ("Gens", lu("v_person", user_key=ENTIER, user_label=TEXTE)),
        ("Auteurs", f'List.Buffer(List.Combine({{{colonne_lue("v_deliverable", "author_key", ENTIER)}, '
                    f'{colonne_lue("v_generation", "author_key", ENTIER)}}}))'),
        ("Resultat", "Table.SelectRows(Gens, each List.Contains(Auteurs, [user_key]))"),
    ])

    bornes = [
        ("Cles", f'List.Buffer(List.RemoveNulls(List.Combine({{{colonne_lue("v_generation", "date_key", ENTIER)}, '
                 f'{colonne_lue("v_deliverable", "approved_date_key", ENTIER)}, '
                 f'{colonne_lue("v_deliverable", "submitted_date_key", ENTIER)}}})))'),
        ("VersDate", VERS_DATE),
        ("Premier", "VersDate(List.Min(Cles, 20260101))"),
        ("Dernier", "VersDate(List.Max(Cles, 20261231))"),
        ("Jours", "List.Dates(Date.StartOfMonth(Premier), "
                  "Duration.Days(Date.EndOfMonth(Dernier) - Date.StartOfMonth(Premier)) + 1, #duration(1, 0, 0, 0))"),
    ]
    t["Calendrier"] = table_tmdl("Calendrier", [
        Col("jour", "Date", DATE, masquee=False), Col("date_key", "Clé de date", ENTIER),
    ], bornes + [
        ("Base", "Table.FromColumns({Jours}, type table [jour = date])"),
        ("AvecCle", f'Table.AddColumn(Base, "date_key", each {CLE_DU_JOUR}, Int64.Type)'),
    ])

    mois = "{" + ", ".join(map(m_texte, MOIS)) + "}"
    cle = "(d as date) as number => Date.Year(d) * 10000 + Date.Month(d) * 100 + Date.Day(d)"
    t["Choix de période"] = table_tmdl("Choix de période", [
        Col("choix", "Période choisie", masquee=False, tri="Rang"), Col("date_key", "Clé de date cible", ENTIER),
        Col("rang", "Rang", ENTIER),
    ], bornes + [
        ("Cle", cle),
        ("Historique", f"List.Transform(Jours, each {{{m_texte(TOUT)}, Cle(_), 0}})"),
        ("Recentes4", 'List.Transform(List.Select(Jours, each _ > Date.AddDays(Dernier, -28) and _ <= Dernier), '
                      'each {"4 dernières semaines", Cle(_), 1})'),
        ("Recentes13", 'List.Transform(List.Select(Jours, each _ > Date.AddDays(Dernier, -91) and _ <= Dernier), '
                       'each {"13 dernières semaines", Cle(_), 2})'),
        ("ParMois", f'List.Transform(Jours, each {{{mois}{{Date.Month(_) - 1}} & " " & Text.From(Date.Year(_)), '
                    "Cle(_), 300000 - (Date.Year(_) * 100 + Date.Month(_))})"),
        ("Resultat", "#table(type table [choix = text, date_key = Int64.Type, rang = Int64.Type], "
                     "Historique & Recentes4 & Recentes13 & ParMois)"),
    ])

    t["Choix du client"] = choix(
        "Choix du client", "Client choisi", TOUS,
        f'List.Combine({{{colonne_lue("v_deliverable", "client_name", TEXTE)}, '
        f'{colonne_lue("v_generation", "client_name", TEXTE)}}})')
    t["Choix du type"] = choix(
        "Choix du type", "Type choisi", TOUS,
        f'let Presents = List.Buffer({colonne_lue("v_deliverable", "type_key", ENTIER)}) in '
        f'Table.Column(Table.SelectRows({types_m()}, each List.Contains(Presents, [type_key])), "libelle")')
    t["Choix du consultant"] = choix(
        "Choix du consultant", "Consultant choisi", TOUS,
        f'let Auteurs = List.Buffer({colonne_lue("v_deliverable", "author_key", ENTIER)}) in '
        f'Table.Column(Table.SelectRows({lu("v_person", user_key=ENTIER, user_label=TEXTE)}, '
        'each List.Contains(Auteurs, [user_key])), "user_label")')

    # Qui est qui pour la RLS : fichier hors entrepôt, jamais versionné (bi/acces.exemple.csv).
    # Absent, il donne une table vide : les rôles Consultant et Responsable ne voient alors rien.
    t["Accès"] = table_tmdl("Accès", [
        Col("utilisateur", "Utilisateur"), Col("user_key", "Clé de personne autorisée", ENTIER),
    ], [
        ("Vide", "#table(type table [utilisateur = text, user_id = text], {})"),
        ("Fichier", 'if Source = "CSV" then (try Table.SelectColumns(Vue("acces"), {"utilisateur", "user_id"}) '
                    "otherwise Vide) else Vide"),
        ("Typage", 'Table.TransformColumnTypes(Fichier, {{"utilisateur", type text}, {"user_id", type text}})'),
        ("Connus", lu("v_person", user_key=ENTIER, user_id=TEXTE)),
        ("Jointure", 'Table.NestedJoin(Typage, {"user_id"}, Connus, {"user_id"}, "p", JoinKind.Inner)'),
        ("AvecCle", 'Table.ExpandTableColumn(Jointure, "p", {"user_key"})'),
        ("Resultat", 'Table.SelectColumns(AvecCle, {"utilisateur", "user_key"})'),
    ], masquee=True)

    regles = [(r.code, r.priority, r.actor, r.label, r.population, r.threshold, r.action, "|".join(r.states))
              for r in pilotage.RULES]
    noms = [("code", "text"), ("priorite", "Int64.Type"), ("acteur", "text"), ("libelle", "text"),
            ("population", "text"), ("seuil", "text"), ("action", "text"), ("etats", "text")]
    t["Règles"] = table_tmdl("Règles", [
        Col("code", "Code de règle"), Col("priorite", "Priorité", ENTIER), Col("acteur", "Acteur"),
        Col("libelle", "Libellé"), Col("population", "Population"), Col("seuil", "Seuil"),
        Col("action", "Action"), Col("etats", "États"),
    ], [("Resultat", m_table(noms, regles))], masquee=True)
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


ACTIVE, INACTIVE, CHOIX = "active", "inactive", "choix"
RELATIONS = [
    ("Générations", "Clé de mission", "Missions", "Clé de mission", ACTIVE),
    ("Sections approuvées", "Clé de mission", "Missions", "Clé de mission", ACTIVE),
    ("Livrables", "Clé de mission", "Missions", "Clé de mission", ACTIVE),
    ("Documents", "Clé de mission", "Missions", "Clé de mission", ACTIVE),
    ("Générations", "Code du type", "Types de livrable", "Code du type", ACTIVE),
    ("Sections approuvées", "Clé de type", "Types de livrable", "Clé de type", ACTIVE),
    ("Livrables", "Clé de type", "Types de livrable", "Clé de type", ACTIVE),
    ("Générations", "Clé de consultant", "Personnes", "Clé de personne", ACTIVE),
    ("Sections approuvées", "Clé de consultant", "Personnes", "Clé de personne", ACTIVE),
    ("Livrables", "Clé de consultant", "Personnes", "Clé de personne", ACTIVE),
    ("Générations", "Clé de date", "Calendrier", "Clé de date", ACTIVE),
    ("Sections approuvées", "Clé de date", "Calendrier", "Clé de date", ACTIVE),
    # La situation courante ne suit pas la période ; les flux l'activent par USERELATIONSHIP.
    ("Livrables", "Clé d'approbation", "Calendrier", "Clé de date", INACTIVE),
    ("Livrables", "Clé de soumission", "Calendrier", "Clé de date", INACTIVE),
    ("Actions", "Identifiant du livrable", "Livrables", "Identifiant du livrable", ACTIVE),
    ("Sections courantes", "Identifiant du livrable", "Livrables", "Identifiant du livrable", ACTIVE),
    ("Série de prévision", "Clé de prévision", "Prévisions", "Clé de prévision", ACTIVE),
    # Segments : le choix filtre la dimension, jamais l'inverse.
    ("Missions", "Client", "Choix du client", "Cible", CHOIX),
    ("Types de livrable", "Type de livrable", "Choix du type", "Cible", CHOIX),
    ("Personnes", "Consultant", "Choix du consultant", "Cible", CHOIX),
    ("Calendrier", "Clé de date", "Choix de période", "Clé de date cible", CHOIX),
]


def relations_tmdl() -> str:
    out = ""
    for i, (a, b, c, e, genre) in enumerate(RELATIONS, 1):
        out += f"relationship r{i:02d}\n"
        if genre == INACTIVE:
            out += "\tisActive: false\n"
        if genre == CHOIX:
            out += "\ttoCardinality: many\n\tcrossFilteringBehavior: oneDirection\n"
        out += f"\tfromColumn: {q(a)}.{q(b)}\n\ttoColumn: {q(c)}.{q(e)}\n\n"
    return out


def roles_tmdl() -> dict[str, str]:
    """Rôles RLS (bi/PUBLICATION.md). Ils ne filtrent que les Lecteurs d'un espace de travail du Service.

    Le filtre est posé sur chaque table qui porte des données : le seul filtre de `Personnes` laisserait
    visibles les missions, les documents, les listes de clients et les prévisions des autres.
    """
    moi = ("CALCULATETABLE(VALUES('Accès'[Clé de personne autorisée]), "
           "'Accès'[Utilisateur] = USERPRINCIPALNAME())")
    mon_acces = "'Accès'[Utilisateur] = USERPRINCIPALNAME()"

    def mes_livrables(colonne_acteur: str, colonne: str) -> str:
        return (f"SELECTCOLUMNS(FILTER(Livrables, Livrables[{colonne_acteur}] IN {moi}), "
                f"\"cle\", Livrables[{colonne}])")

    def perimetre(colonne_acteur: str) -> dict[str, str]:
        missions = mes_livrables(colonne_acteur, "Clé de mission")
        return {
            "Livrables": f"Livrables[{colonne_acteur}] IN {moi}",
            "Missions": f"'Missions'[Clé de mission] IN {missions}",
            "Choix du client": ("'Choix du client'[Cible] IN SELECTCOLUMNS(FILTER(Missions, "
                                f"Missions[Clé de mission] IN {missions}), \"client\", Missions[Client])"),
            "Accès": mon_acces,
        }

    def personnes(cles: str) -> dict[str, str]:
        return {
            "Personnes": f"'Personnes'[Clé de personne] IN {cles}",
            "Choix du consultant": ("'Choix du consultant'[Cible] IN SELECTCOLUMNS(FILTER(Personnes, "
                                    f"Personnes[Clé de personne] IN {cles}), \"nom\", Personnes[Consultant])"),
        }

    prevu_auteur = f"'Prévisions'[Clé de personne prévue] IN {moi}"
    prevu_relecteur = f"'Prévisions'[Clé de responsable prévu] IN {moi}"
    roles = {
        "Consultant": {**perimetre("Clé de consultant"), **personnes(moi), "Prévisions": prevu_auteur},
        "Responsable": {**perimetre("Clé de responsable"),
                        **personnes(mes_livrables("Clé de responsable", "Clé de consultant")),
                        "Prévisions": prevu_relecteur},
        "Administration": {},
    }
    out = {}
    for nom, filtres in roles.items():
        texte = f"role {q(nom)}\n\tmodelPermission: read\n"
        for table, dax in filtres.items():
            texte += f"\n\ttablePermission {q(table)} = {dax}\n"
        out[nom] = texte
    return out


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
        "\t\t    SansVides = Table.ReplaceValue(Brut, \"\", null, Replacer.ReplaceValue, Table.ColumnNames(Brut)),\n"
        f"\t\t    Booleens = List.Intersect({{Table.ColumnNames(SansVides), {booleens}}}),\n"
        "\t\t    Numerique = Table.TransformColumns(SansVides, List.Transform(Booleens, (c) => {c, (v) =>\n"
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
           + "".join(f"ref role {q(n)}\n" for n in roles_tmdl()) + "\n"
           + "".join(f"ref expression {n}\n" for n in
                     ("Source", "DossierCsv", "CultureCsv", "PgServer", "PgDatabase", "Vue")))
    ecrire(d / "expressions.tmdl", expressions(dossier_csv))
    for nom, texte in tables.items():
        ecrire(d / "tables" / f"{nom}.tmdl", texte)
    ecrire(d / "relationships.tmdl", relations_tmdl())
    for nom, texte in roles_tmdl().items():
        ecrire(d / "roles" / f"{nom}.tmdl", texte)
