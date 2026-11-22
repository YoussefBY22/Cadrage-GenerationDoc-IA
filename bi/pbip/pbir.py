"""Briques PBIR : expressions, objets de formatage et conteneurs de visuels."""
from __future__ import annotations

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
SCHEMA_VISUEL = f"{SCHEMA}/visualContainer/2.7.0/schema.json"
MESURES = "Indicateurs"
SEMIBOLD = "Segoe UI Semibold"


def col(table: str, colonne: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": colonne}}


def mes(nom: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": MESURES}}, "Property": nom}}


def ref(champ: dict) -> str:
    (corps,) = champ.values()
    return f"{corps['Expression']['SourceRef']['Entity']}.{corps['Property']}"


def val(v) -> dict:
    """Valeur de propriété : littéral typé, ou mesure (mise en forme conditionnelle, titre dynamique)."""
    if isinstance(v, dict):
        return {"expr": v} if "Measure" in v else v
    if isinstance(v, bool):
        texte = "true" if v else "false"
    elif isinstance(v, int):
        texte = f"{v}L"
    elif isinstance(v, float):
        texte = f"{v:g}D"
    else:
        texte = "'" + v.replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": texte}}}


def couleur(c) -> dict:
    return {"solid": {"color": val(c)}}


def est_couleur(cle: str, v) -> bool:
    if isinstance(v, str):
        return v.startswith("#")
    return isinstance(v, dict) and "Measure" in v and (cle.lower().endswith("color") or "fill" in cle.lower())


def props(selecteur: dict | None = None, /, **kw) -> dict:
    """Un objet de formatage. Les entiers deviennent `L`, les flottants `D`, les « #RRGGBB » des couleurs."""
    objet: dict = {"properties": {k: couleur(v) if est_couleur(k, v) else val(v) for k, v in kw.items()}}
    if selecteur:
        objet["selector"] = selecteur
    return objet


DEFAUT = {"id": "default"}
CHAQUE_POINT = {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}


def serie(champ: dict) -> dict:
    return {"metadata": ref(champ)}


def categorie(champ: dict, valeur: str) -> dict:
    return {"data": [{"scopeId": {"Comparison": {
        "ComparisonKind": 0, "Left": champ, "Right": {"Literal": {"Value": "'" + valeur.replace("'", "''") + "'"}}}}}]}


def projection(champ: dict, libelle: str | None = None) -> dict:
    (corps,) = champ.values()
    p = {"field": champ, "queryRef": ref(champ), "nativeQueryRef": corps["Property"]}
    if "Column" in champ:
        p["active"] = True
    if libelle:
        p["displayName"] = libelle
    return p


def requete(roles: dict[str, list], tri: tuple[dict, str] | None = None) -> dict:
    """`roles` : rôle → champs, chacun seul ou en paire (champ, libellé affiché)."""
    etat = {}
    for role, champs in roles.items():
        etat[role] = {"projections": [projection(*c) if isinstance(c, tuple) else projection(c) for c in champs]}
    q: dict = {"queryState": etat}
    if tri:
        q["sortDefinition"] = {"sort": [{"field": tri[0], "direction": tri[1]}], "isDefaultSort": False}
    return q
