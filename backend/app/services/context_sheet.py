"""Fiche de contexte (FR-25) : lecture, enregistrement, confirmation. Rien n'y entre sans un humain."""

from app.domain.context import PROJECT_TYPE_LABELS, ContextData, ContextSheet
from app.domain.workflow import CurrentUser
from app.security import injection


def get(repo, dossier_id: str) -> ContextSheet:
    """Fiche du dossier ; vide et non confirmée si personne ne l'a encore remplie."""
    sheet = repo.get_context(dossier_id)
    return sheet or ContextSheet(dossier_id=dossier_id, data=ContextData())


def save(repo, dossier_id: str, user: CurrentUser, changes: dict, *,
         confirm: bool = False) -> ContextSheet:
    """Fusionne `changes` dans la fiche. Toute modification retire la confirmation."""
    current = get(repo, dossier_id).data.model_dump()
    current.update({k: v for k, v in changes.items() if v is not None})
    data = ContextData.model_validate(current)
    data = data.model_copy(update={"project_types": list(dict.fromkeys(data.project_types))})
    sheet = repo.save_context(dossier_id, data, user_id=user.id, confirmed=confirm)
    repo.audit(user.id, "context.confirm" if confirm else "context.save", "dossier", dossier_id,
               {"fields": sorted(changes), "confirmed": confirm})
    return sheet


def confirm(repo, dossier_id: str, user: CurrentUser) -> ContextSheet:
    return save(repo, dossier_id, user, {}, confirm=True)


def prompt_lines(sheet: ContextSheet, lang: str = "fr", *, only_confirmed: bool = True) -> str:
    """Résumé court de la fiche pour le prompt : un cadre, jamais une source.

    La génération n'utilise que la fiche confirmée ; le chat lit aussi le brouillon.
    """
    if only_confirmed and not sheet.confirmed:
        return ""
    d = sheet.data
    labels = PROJECT_TYPE_LABELS.get(lang, PROJECT_TYPE_LABELS["fr"])
    fr = lang != "en"
    parts = [
        (("secteur" if fr else "sector"), d.sector), (("taille" if fr else "size"), d.size),
        (("pays" if fr else "country"), d.country),
        (("type de projet" if fr else "project type"),
         ", ".join(labels[t] for t in d.project_types)),
        (("périmètre" if fr else "scope"), d.scope),
        (("contraintes" if fr else "constraints"), d.constraints),
        (("parties prenantes" if fr else "stakeholders"), d.stakeholders),
        (("axes de la feuille de route" if fr else "roadmap axes"), d.roadmap_axes)]
    return " ; ".join(f"{k} : {v}" for k, v in parts if v)


def flags(sheet_data: ContextData) -> list[str]:
    """Codes d'injection détectés dans la fiche (affichés, jamais bloquants pour la saisie)."""
    out: list[str] = []
    for f in ("sector", "size", "country", "language", "scope", "constraints", "stakeholders", "roadmap_axes"):
        out += [c for c in injection.scan(getattr(sheet_data, f)) if c not in out]
    return out
