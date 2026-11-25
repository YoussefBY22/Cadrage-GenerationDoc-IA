"""Modèle sémantique TMDL : étoile en français au-dessus des vues de l'entrepôt (docs/07 §4).

Les noms techniques des vues ne sont conservés que comme `sourceColumn` ; le rapport ne voit que les libellés.
Chaque segment porte une vraie valeur « Tous » (table de choix reliée en plusieurs-à-plusieurs) : le libellé
ne dépend donc pas de la langue de Power BI Desktop. Aucune clé technique n'est visible : chaque code a son libellé.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from indicateurs import ERREURS, TOUS, TOUS_MOIS, TOUTES_DONNEES, toutes

ENTIER, DECIMAL, TEXTE, DATE = "int64", "double", "string", "dateTime"
M_TYPE = {ENTIER: "Int64.Type", DECIMAL: "type number", TEXTE: "type text", DATE: "type date"}
BOOLEENS = ["is_demo", "returned", "refused", "first_rejected", "validated", "adopted", "is_best"]


@dataclass(frozen=True)
class Col:
    source: str
    nom: str
    type: str = TEXTE
    masquee: bool = True
    tri: str | None = None
    ajoutee: bool = False  # colonne créée dans Power Query, absente de la vue
    categorie: str | None = None  # ex. ImageUrl : le logo s'affiche comme une image


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
        out.append("\t\tformatString: dd/MM/yyyy")
    if c.categorie:
        out.append(f"\t\tdataCategory: {c.categorie}")
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
TYPES = [(1, "findings", "Constats"), (2, "roadmap", "Feuille de route"),
         (3, "tor", "Termes de référence"), (4, "cdc", "Cahier des charges")]
TYPES_COURTS = {"findings": "Constats", "roadmap": "Feuille de route", "tor": "TdR", "cdc": "CdC"}
ETATS = [("draft", "Brouillon", 1), ("in_review", "En relecture", 2), ("approved", "Approuvé", 3),
         ("rejected", "Renvoyé", 4)]
GRAVITES = [("high", "Élevée", 1), ("medium", "Moyenne", 2), ("low", "Faible", 3)]
CONTROLES = {"ok": "Cohérent", "ecart": "Écart", "non_detectees": "Non détectées",
             "non_lu": "Pas encore lu"}
STATUTS_RECO = {"proposed": "À valider", "validated": "Validée", "deleted": "Supprimée", "merged": "Fusionnée"}
ORIGINES = {"rules": "Relevée dans le rapport", "consultant": "Ajoutée par le consultant"}
RESULTATS = {"ok": "Réussi", "refused": "Refus voulu (preuve insuffisante)", "invalid": "Sortie invalide"}
AVEC_ERREUR = "Réussi, avec phrase ou citation fautive"
MODELES = {"base": "Modèle de base", "essai1": "Essai 1", "v4": "v4 (adopté)", "v5": "v5"}
MOIS = ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."]
VERS_DATE = ("(k as number) as date => #date(Number.IntegerDivide(k, 10000), "
             "Number.Mod(Number.IntegerDivide(k, 100), 100), Number.Mod(k, 100))")
DEMO, REEL = "Démonstration", "Réelles"


def libelle_modele() -> str:
    """« ollama:cadrage-4b-lora » → « Qwen3-4B + LoRA v4 » ; tout modèle de démo porte [DÉMO]."""
    return ('each if [is_demo] = 1 then "[DÉMO] modèle de démonstration" '
            'else if Text.Contains([model_name] ?? "", "lora") then "Qwen3-4B + LoRA v4 (adopté)" '
            'else if Text.Contains([model_name] ?? "", "base") then "Qwen3-4B de base" '
            'else [model_name] ?? "Inconnu", type text')


def sections_m() -> str:
    """Libellé lisible et rôle de chaque section, lus dans les gabarits (backend/app/generation/templates)."""
    from sections import sections
    return m_table([("cle", "text"), ("libelle", "text"), ("role", "text"), ("livrable", "text")], sections())


def types_m() -> str:
    return m_table([("type_key", "Int64.Type"), ("type_code", "text"), ("libelle", "text"), ("court", "text")],
                   [(k, c, lib, TYPES_COURTS[c]) for k, c, lib in TYPES])


def ordre(colonne: str, paires: dict[str, int]) -> str:
    texte = {k: str(v) for k, v in paires.items()}
    return f'each Number.From(Record.FieldOrDefault({m_libelles(texte)}, [{colonne}], "9")), Int64.Type'


# ---------------------------------------------------------------- tables de faits
def tables_de_faits() -> dict[str, str]:
    t = {}

    cols = [
        Col("date_key", "Clé de date", ENTIER), Col("mission_key", "Clé de mission", ENTIER),
        Col("author_key", "Clé de consultant", ENTIER), Col("type_code", "Code du type"),
        Col("section_code", "Code de section"), Col("model_name", "Nom du modèle"),
        Col("status", "Statut"), Col("sentences_total", "Phrases produites", ENTIER),
        Col("sentences_verified", "Phrases validées", ENTIER),
        Col("sentences_warning", "Phrases à revoir", ENTIER),
        Col("sentences_failed", "Phrases non vérifiées", ENTIER),
        Col("citations_total", "Citations produites", ENTIER),
        Col("citations_valid", "Citations valides", ENTIER),
        Col("latency_ms", "Durée en ms", ENTIER), Col("is_demo", "Est une démonstration", ENTIER),
        Col("cle_section", "Clé de section", ajoutee=True),
        Col("resultat", "Résultat", masquee=False, ajoutee=True),
        Col("modele", "Modèle", masquee=False, ajoutee=True),
        Col("en_erreur", "En erreur", ENTIER, ajoutee=True),
    ]
    t["Générations"] = table_tmdl("Générations", cols, depuis_vue("v_generation", cols) + [
        ("AvecSection", 'Table.AddColumn(Typage, "cle_section", each [type_code] & "|" & [section_code], type text)'),
        # Un refus faute de preuve est le comportement voulu : ce n'est pas une erreur.
        ("AvecErreur", 'Table.AddColumn(AvecSection, "en_erreur", each if [status] = "invalid" or '
                       '([status] = "ok" and ([sentences_failed] > 0 or [citations_valid] < [citations_total])) '
                       'then 1 else 0, Int64.Type)'),
        ("AvecResultat", f'Table.AddColumn(AvecErreur, "resultat", each if [status] = "ok" and [en_erreur] = 1 then '
                         f'{m_texte(AVEC_ERREUR)} else Record.FieldOrDefault({m_libelles(RESULTATS)}, [status], "Autre"), '
                         'type text)'),
        ("AvecModele", f'Table.AddColumn(AvecResultat, "modele", {libelle_modele()})'),
    ])

    cols = [
        Col("deliverable_id", "Identifiant du livrable"), Col("mission_key", "Clé de mission", ENTIER),
        Col("type_key", "Clé de type", ENTIER), Col("author_key", "Clé de consultant", ENTIER),
        Col("reviewer_key", "Clé de responsable", ENTIER), Col("created_date_key", "Clé de création", ENTIER),
        Col("state", "Code d'état"), Col("blocking_open", "Phrases bloquantes", ENTIER),
        Col("citations_invalid", "Citations sans source", ENTIER),
        Col("etat", "État", masquee=False, ajoutee=True, tri="Ordre d'état"),
        Col("ordre", "Ordre d'état", ENTIER, ajoutee=True),
    ]
    t["Livrables"] = table_tmdl("Livrables", cols, depuis_vue("v_deliverable", cols) + [
        ("AvecEtat", f'Table.AddColumn(Typage, "etat", {m_libelle("state", {c: l for c, l, _ in ETATS}, "Inconnu")})'),
        ("AvecOrdre", f'Table.AddColumn(AvecEtat, "ordre", {ordre("state", {c: o for c, _, o in ETATS})})'),
    ])

    cols = [
        Col("finding_id", "Identifiant du constat"), Col("mission_key", "Clé de mission", ENTIER),
        Col("severity", "Code de gravité"), Col("axis", "Axe", masquee=False),
        Col("validated", "Validé", ENTIER),
        Col("gravite", "Gravité", masquee=False, ajoutee=True, tri="Ordre de gravité"),
        Col("ordre", "Ordre de gravité", ENTIER, ajoutee=True),
    ]
    t["Constats"] = table_tmdl("Constats", cols, depuis_vue("v_finding", cols) + [
        ("AvecGravite", f'Table.AddColumn(Typage, "gravite", '
                        f'{m_libelle("severity", {c: l for c, l, _ in GRAVITES}, "Non précisée")})'),
        ("AvecOrdre", f'Table.AddColumn(AvecGravite, "ordre", {ordre("severity", {c: o for c, _, o in GRAVITES})})'),
    ])

    cols = [
        Col("initiative_id", "Identifiant de l'initiative"), Col("mission_key", "Clé de mission", ENTIER),
        Col("axis", "Axe de l'initiative", masquee=False), Col("wave", "Numéro de vague", ENTIER),
        Col("rank", "Rang", ENTIER), Col("findings", "Constats traités", ENTIER),
        Col("vague", "Vague", masquee=False, ajoutee=True, tri="Numéro de vague"),
    ]
    t["Initiatives"] = table_tmdl("Initiatives", cols, depuis_vue("v_initiative", cols) + [
        ("AvecVague", 'Table.AddColumn(Typage, "vague", each "Vague " & Text.From([wave] ?? 0), type text)'),
    ])

    cols = [
        Col("document_key", "Clé de document", ENTIER), Col("mission_key", "Clé de mission", ENTIER),
        Col("report_label", "Rapport", masquee=False), Col("pages", "Pages", ENTIER),
        Col("expected", "Annoncées", ENTIER), Col("extracted", "Retenues", ENTIER),
        Col("validated", "Validées", ENTIER), Col("missing", "Manquantes", ENTIER),
        Col("duplicates", "Doublons", ENTIER), Col("missing_list", "Numéros manquants"),
        Col("status", "Code du contrôle"),
        Col("controle", "Contrôle", masquee=False, ajoutee=True),
        Col("alerte", "En alerte", ENTIER, ajoutee=True),
        Col("projet", "Projet du rapport", masquee=False, ajoutee=True),
    ]
    t["Rapports"] = table_tmdl("Rapports", cols, depuis_vue("v_report_check", cols) + [
        ("AvecControle", f'Table.AddColumn(Typage, "controle", {m_libelle("status", CONTROLES, "Inconnu")})'),
        ("AvecAlerte", 'Table.AddColumn(AvecControle, "alerte", each if List.Contains({"ecart", "non_detectees"}, '
                       '[status]) then 1 else 0, Int64.Type)'),
        ("Noms", lu("v_project", mission_key=ENTIER, mission_name=TEXTE)),
        ("Jointure", 'Table.NestedJoin(AvecAlerte, {"mission_key"}, Noms, {"mission_key"}, "p", JoinKind.LeftOuter)'),
        ("AvecNom", 'Table.ExpandTableColumn(Jointure, "p", {"mission_name"})'),
        ("AvecProjet", 'Table.AddColumn(AvecNom, "projet", each [mission_name], type text)'),
        ("Utiles", 'Table.RemoveColumns(AvecProjet, {"mission_name"})'),
    ])

    cols = [
        Col("recommendation_id", "Identifiant de la recommandation"), Col("document_key", "Clé de document", ENTIER),
        Col("number", "Numéro", ENTIER), Col("page", "Page", ENTIER), Col("status", "Code du statut"),
        Col("origin", "Code de l'origine"),
        Col("statut", "Statut", masquee=False, ajoutee=True), Col("origine", "Origine", masquee=False, ajoutee=True),
        Col("active", "Active", ENTIER, ajoutee=True),
    ]
    t["Recommandations"] = table_tmdl("Recommandations", cols, depuis_vue("v_recommendation", cols) + [
        ("AvecStatut", f'Table.AddColumn(Typage, "statut", {m_libelle("status", STATUTS_RECO, "Inconnu")})'),
        ("AvecOrigine", f'Table.AddColumn(AvecStatut, "origine", {m_libelle("origin", ORIGINES, "Inconnue")})'),
        ("AvecActive", 'Table.AddColumn(AvecOrigine, "active", each if List.Contains({"proposed", "validated"}, '
                       '[status]) then 1 else 0, Int64.Type)'),
    ])

    cols = [
        Col("run_id", "Code de l'essai"), Col("label", "Essai", masquee=False, tri="Clé de date d'essai"),
        Col("run_date_key", "Clé de date d'essai", ENTIER), Col("platform", "Plateforme", masquee=False),
        Col("gpu", "GPU", masquee=False), Col("examples", "Exemples d'entraînement", ENTIER),
        Col("test_examples", "Exemples de test", ENTIER), Col("duration_min", "Durée en minutes", DECIMAL),
        Col("stop_step", "Pas d'arrêt", ENTIER), Col("best_step", "Meilleur pas", ENTIER),
        Col("best_val_loss", "Meilleure erreur de validation", DECIMAL), Col("adopted", "Adopté", ENTIER),
        Col("outcome", "Résultat de l'essai", masquee=False),
        Col("date", "Date de l'essai", DATE, masquee=False, ajoutee=True),
    ]
    t["Entraînements"] = table_tmdl("Entraînements", cols, depuis_vue("v_training_run", cols) + [
        ("VersDate", VERS_DATE),
        ("AvecDate", 'Table.AddColumn(Typage, "date", each VersDate([run_date_key]), type date)'),
    ])

    cols = [Col("run_id", "Code de l'essai"), Col("step", "Pas", ENTIER, masquee=False),
            Col("val_loss", "Erreur de validation", DECIMAL), Col("is_best", "Meilleur", ENTIER)]
    t["Courbe de validation"] = table_tmdl("Courbe de validation", cols, depuis_vue("v_training_point", cols))

    cols = [Col("run_id", "Code de l'essai"), Col("model", "Code du modèle"), Col("task", "Tâche", masquee=False),
            Col("correct", "Réussis", ENTIER), Col("total", "Total", ENTIER),
            Col("modele", "Modèle testé", masquee=False, ajoutee=True, tri="Ordre du modèle"),
            Col("ordre", "Ordre du modèle", ENTIER, ajoutee=True)]
    t["Scores"] = table_tmdl("Scores", cols, depuis_vue("v_training_score", cols) + [
        ("AvecModele", f'Table.AddColumn(Typage, "modele", {m_libelle("model", MODELES, "Autre")})'),
        ("AvecOrdre", f'Table.AddColumn(AvecModele, "ordre", {ordre("model", {k: i for i, k in enumerate(MODELES)})})'),
    ])
    return t


# ---------------------------------------------------------------- dimensions et choix
def choix(nom: str, libelle: str, tous: str, valeurs: str, rangs: str | None = None,
          avant: list[tuple[str, str]] | None = None) -> str:
    """Table de segment : « Tous » pointe vers chaque membre, chaque membre vers lui-même.

    `rangs` : liste M parallèle à `valeurs` qui donne l'ordre (sinon l'ordre alphabétique).
    """
    if rangs is None:
        etapes = [("Valeurs", f"List.Buffer(List.Sort(List.Distinct(List.RemoveNulls({valeurs}))))")]
    else:
        etapes = [("Paires", f"List.Distinct(List.Zip({{{valeurs}, {rangs}}}))"),
                  ("Triees", "List.Sort(List.Select(Paires, each _{0} <> null), (a, b) => Value.Compare(a{1}, b{1}))"),
                  ("Valeurs", "List.Buffer(List.Transform(Triees, each _{0}))")]
    return table_tmdl(nom, [
        Col("choix", libelle, masquee=False, tri="Rang"), Col("cible", "Cible"), Col("rang", "Rang", ENTIER),
    ], (avant or []) + etapes + [
        ("Toutes", f"List.Transform(Valeurs, each {{{m_texte(tous)}, _, 0}})"),
        ("Chacune", "List.Transform(List.Positions(Valeurs), each {Valeurs{_}, Valeurs{_}, _ + 1})"),
        ("Resultat", '#table(type table [choix = text, cible = text, rang = Int64.Type], Toutes & Chacune)'),
    ])


def dimensions() -> dict[str, str]:
    t = {}
    cols = [
        Col("mission_key", "Clé de mission", ENTIER), Col("mission_name", "Projet", masquee=False),
        Col("client_name", "Client", masquee=False), Col("sector", "Secteur", masquee=False),
        Col("request_summary", "Demande du client", masquee=False),
        Col("start_date_key", "Clé de début", ENTIER), Col("end_date_key", "Clé de fin", ENTIER),
        Col("logo", "Logo", masquee=False, categorie="ImageUrl"),
        Col("documents", "Documents", ENTIER), Col("audit_reports", "Rapports d'audit", ENTIER),
        Col("is_demo", "Est une démonstration", ENTIER),
        Col("donnees", "Données", masquee=False, ajoutee=True),
        Col("debut", "Début", DATE, masquee=False, ajoutee=True), Col("fin", "Fin", DATE, masquee=False, ajoutee=True),
    ]
    t["Projets"] = table_tmdl("Projets", cols, depuis_vue("v_project", cols) + [
        ("VersDate", VERS_DATE),
        ("AvecDonnees", f'Table.AddColumn(Typage, "donnees", each if [is_demo] = 1 then {m_texte(DEMO)} '
                        f'else {m_texte(REEL)}, type text)'),
        ("AvecDebut", 'Table.AddColumn(AvecDonnees, "debut", each if [start_date_key] = null then null '
                      'else VersDate([start_date_key]), type date)'),
        ("AvecFin", 'Table.AddColumn(AvecDebut, "fin", each if [end_date_key] = null then null '
                    'else VersDate([end_date_key]), type date)'),
    ])

    t["Types de livrable"] = table_tmdl("Types de livrable", [
        Col("type_key", "Clé de type", ENTIER), Col("type_code", "Code du type"),
        Col("libelle", "Type de livrable", masquee=False, tri="Clé de type"),
        Col("court", "Type", masquee=False, tri="Clé de type"),
    ], [("Resultat", types_m())])

    t["Sections"] = table_tmdl("Sections", [
        Col("cle", "Clé de section"), Col("libelle", "Section", masquee=False),
        Col("role", "À quoi sert la section", masquee=False), Col("livrable", "Livrable de la section", masquee=False),
    ], [("Gabarits", sections_m()),
        ("Vues", lu("v_generation", type_code=TEXTE, section_code=TEXTE, section_title=TEXTE)),
        ("Cles", 'Table.Distinct(Table.AddColumn(Vues, "cle", each [type_code] & "|" & [section_code], type text), {"cle"})'),
        ("Absentes", 'Table.SelectRows(Cles, each not List.Contains(Gabarits[cle], [cle]))'),
        ("AvecLibelle", 'Table.AddColumn(Absentes, "libelle", each [section_title], type text)'),
        ("AvecRole", 'Table.AddColumn(AvecLibelle, "role", each "Section sans description dans les gabarits", type text)'),
        ("AvecLivrable", f'Table.AddColumn(AvecRole, "livrable", each Record.FieldOrDefault('
                         f'{m_libelles(TYPES_COURTS)}, [type_code], "Autre"), type text)'),
        ("Resultat", 'Table.Combine({Gabarits, Table.SelectColumns(AvecLivrable, {"cle", "libelle", "role", "livrable"})})')])

    t["Types d'erreur"] = table_tmdl("Types d'erreur", [
        Col("code", "Code d'erreur"), Col("libelle", "Type d'erreur", masquee=False, tri="Ordre d'erreur"),
        Col("ordre", "Ordre d'erreur", ENTIER), Col("explication", "Explication", masquee=False),
    ], [("Resultat", m_table([("code", "text"), ("libelle", "text"), ("ordre", "Int64.Type"), ("explication", "text")],
                             ERREURS))])

    t["Personnes"] = table_tmdl("Personnes", [
        Col("user_key", "Clé de personne", ENTIER), Col("user_label", "Consultant", masquee=False),
    ], [
        ("Gens", lu("v_person", user_key=ENTIER, user_label=TEXTE)),
        ("Auteurs", f'List.Buffer(List.Combine({{{colonne_lue("v_deliverable", "author_key", ENTIER)}, '
                    f'{colonne_lue("v_generation", "author_key", ENTIER)}}}))'),
        ("Resultat", "Table.SelectRows(Gens, each List.Contains(Auteurs, [user_key]))"),
    ])

    mois = "{" + ", ".join(map(m_texte, MOIS)) + "}"
    bornes = [
        ("Cles", f'List.Buffer(List.RemoveNulls(List.Combine({{{colonne_lue("v_generation", "date_key", ENTIER)}, '
                 f'{colonne_lue("v_deliverable", "created_date_key", ENTIER)}}})))'),
        ("VersDate", VERS_DATE),
        ("Premier", "VersDate(List.Min(Cles, 20260101))"),
        ("Dernier", "VersDate(List.Max(Cles, 20261231))"),
        ("Jours", "List.Dates(Date.StartOfMonth(Premier), "
                  "Duration.Days(Date.EndOfMonth(Dernier) - Date.StartOfMonth(Premier)) + 1, #duration(1, 0, 0, 0))"),
        ("NomMois", f'(d as date) as text => {mois}{{Date.Month(d) - 1}} & " " & Text.From(Date.Year(d))'),
    ]
    t["Calendrier"] = table_tmdl("Calendrier", [
        Col("jour", "Date", DATE, masquee=False), Col("date_key", "Clé de date", ENTIER),
        Col("mois_key", "Clé de mois", ENTIER), Col("mois", "Mois", masquee=False, tri="Clé de mois"),
        Col("jour_court", "Jour", masquee=False, tri="Clé de date"),
        Col("semaine_key", "Clé de semaine", ENTIER),
        Col("semaine", "Semaine", masquee=False, tri="Clé de semaine"),
    ], bornes + [
        ("Base", "Table.FromColumns({Jours}, type table [jour = date])"),
        ("AvecCle", 'Table.AddColumn(Base, "date_key", each Date.Year([jour]) * 10000 + Date.Month([jour]) * 100 '
                    '+ Date.Day([jour]), Int64.Type)'),
        ("AvecMoisCle", 'Table.AddColumn(AvecCle, "mois_key", each Date.Year([jour]) * 100 + Date.Month([jour]), '
                        'Int64.Type)'),
        ("AvecMois", 'Table.AddColumn(AvecMoisCle, "mois", each NomMois([jour]), type text)'),
        ("AvecJour", 'Table.AddColumn(AvecMois, "jour_court", each Text.PadStart(Text.From(Date.Day([jour])), 2, "0") '
                     '& "/" & Text.PadStart(Text.From(Date.Month([jour])), 2, "0"), type text)'),
        ("Lundi", "(d as date) as date => Date.StartOfWeek(d, Day.Monday)"),
        ("AvecSemaineCle", 'Table.AddColumn(AvecJour, "semaine_key", each Date.Year(Lundi([jour])) * 10000 + '
                           'Date.Month(Lundi([jour])) * 100 + Date.Day(Lundi([jour])), Int64.Type)'),
        ("AvecSemaine", 'Table.AddColumn(AvecSemaineCle, "semaine", each '
                        'Text.PadStart(Text.From(Date.Day(Lundi([jour]))), 2, "0") & "/" & '
                        'Text.PadStart(Text.From(Date.Month(Lundi([jour]))), 2, "0"), type text)'),
    ])
    t["Choix du mois"] = choix("Choix du mois", "Mois choisi", TOUS_MOIS, "List.Transform(Jours, each NomMois(_))",
                               "List.Transform(Jours, each Date.Year(_) * 100 + Date.Month(_))", avant=bornes)
    t["Choix des données"] = choix("Choix des données", "Données choisies", TOUTES_DONNEES,
                                   f"{{{m_texte(REEL)}, {m_texte(DEMO)}}}", "{1, 2}")
    t["Choix du projet"] = choix("Choix du projet", "Projet choisi", TOUS,
                                 colonne_lue("v_project", "mission_name", TEXTE))
    t["Choix du client"] = choix("Choix du client", "Client choisi", TOUS,
                                 colonne_lue("v_project", "client_name", TEXTE))
    t["Choix du type"] = choix("Choix du type", "Type choisi", TOUS, "{" + ", ".join(m_texte(l) for _, _, l in TYPES) + "}",
                               "{1, 2, 3, 4}")
    t["Choix du consultant"] = choix(
        "Choix du consultant", "Consultant choisi", TOUS,
        f'let Auteurs = List.Buffer(List.Combine({{{colonne_lue("v_deliverable", "author_key", ENTIER)}, '
        f'{colonne_lue("v_generation", "author_key", ENTIER)}}})) in '
        f'Table.Column(Table.SelectRows({lu("v_person", user_key=ENTIER, user_label=TEXTE)}, '
        'each List.Contains(Auteurs, [user_key])), "user_label")')

    # Qui est qui pour la RLS : fichier hors entrepôt, jamais versionné (bi/acces.exemple.csv).
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


ACTIVE, CHOIX = "active", "choix"
RELATIONS = [
    ("Générations", "Clé de mission", "Projets", "Clé de mission", ACTIVE),
    ("Livrables", "Clé de mission", "Projets", "Clé de mission", ACTIVE),
    ("Constats", "Clé de mission", "Projets", "Clé de mission", ACTIVE),
    ("Initiatives", "Clé de mission", "Projets", "Clé de mission", ACTIVE),
    ("Rapports", "Clé de mission", "Projets", "Clé de mission", ACTIVE),
    ("Recommandations", "Clé de document", "Rapports", "Clé de document", ACTIVE),
    ("Générations", "Code du type", "Types de livrable", "Code du type", ACTIVE),
    ("Livrables", "Clé de type", "Types de livrable", "Clé de type", ACTIVE),
    ("Générations", "Clé de consultant", "Personnes", "Clé de personne", ACTIVE),
    ("Livrables", "Clé de consultant", "Personnes", "Clé de personne", ACTIVE),
    ("Générations", "Clé de date", "Calendrier", "Clé de date", ACTIVE),
    ("Livrables", "Clé de création", "Calendrier", "Clé de date", ACTIVE),
    ("Générations", "Clé de section", "Sections", "Clé de section", ACTIVE),
    ("Courbe de validation", "Code de l'essai", "Entraînements", "Code de l'essai", ACTIVE),
    ("Scores", "Code de l'essai", "Entraînements", "Code de l'essai", ACTIVE),
    # Segments : le choix filtre la dimension, jamais l'inverse.
    ("Projets", "Données", "Choix des données", "Cible", CHOIX),
    ("Projets", "Projet", "Choix du projet", "Cible", CHOIX),
    ("Projets", "Client", "Choix du client", "Cible", CHOIX),
    ("Types de livrable", "Type de livrable", "Choix du type", "Cible", CHOIX),
    ("Personnes", "Consultant", "Choix du consultant", "Cible", CHOIX),
    ("Calendrier", "Mois", "Choix du mois", "Cible", CHOIX),
]


def relations_tmdl() -> str:
    out = ""
    for i, (a, b, c, e, genre) in enumerate(RELATIONS, 1):
        out += f"relationship r{i:02d}\n"
        if genre == CHOIX:
            out += "\ttoCardinality: many\n\tcrossFilteringBehavior: oneDirection\n"
        out += f"\tfromColumn: {q(a)}.{q(b)}\n\ttoColumn: {q(c)}.{q(e)}\n\n"
    return out


def roles_tmdl() -> dict[str, str]:
    """Rôles RLS (bi/PUBLICATION.md), effectifs seulement pour les Lecteurs d'un espace du Service.

    Un consultant voit les projets où il a rédigé ou généré ; un responsable, ceux où il relit.
    """
    moi = ("CALCULATETABLE(VALUES('Accès'[Clé de personne autorisée]), "
           "'Accès'[Utilisateur] = USERPRINCIPALNAME())")
    acces = "'Accès'[Utilisateur] = USERPRINCIPALNAME()"

    def projets(colonne: str, aussi_generations: bool) -> str:
        cles = f'SELECTCOLUMNS(FILTER(Livrables, Livrables[{colonne}] IN {moi}), "k", Livrables[Clé de mission])'
        if aussi_generations:
            cles = (f"UNION({cles}, SELECTCOLUMNS(FILTER('Générations', 'Générations'[Clé de consultant] IN {moi}), "
                    "\"k\", 'Générations'[Clé de mission]))")
        return f"'Projets'[Clé de mission] IN {cles}"

    roles = {
        "Consultant": {"Projets": projets("Clé de consultant", True),
                       "Personnes": f"'Personnes'[Clé de personne] IN {moi}", "Accès": acces},
        "Responsable": {"Projets": projets("Clé de responsable", False), "Accès": acces},
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
