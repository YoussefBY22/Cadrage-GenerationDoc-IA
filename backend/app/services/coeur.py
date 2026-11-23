"""Priorités institutionnelles et projets existants : saisie humaine, validation, contrôles de forme."""

from app.domain.coeur import ExistingProject, Priority
from app.domain.workflow import CurrentUser

from .generation import GenerationError


def _check_sources(repo, dossier_id: str, source_ids: list[str]) -> list[str]:
    ids = list(dict.fromkeys(source_ids))
    known = repo.get_chunks(dossier_id, ids)
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise GenerationError(422, "UNKNOWN_SOURCE",
                              "Passage inconnu dans ce dossier : " + ", ".join(unknown))
    roles = repo.document_roles(dossier_id)
    trames = [i for i in ids if roles.get(known[i].document_id) == "template"]
    if trames:  # une trame n'est jamais une source
        raise GenerationError(422, "TEMPLATE_SOURCE",
                              "Une trame ne peut pas être citée comme source : " + ", ".join(trames))
    return ids


def can_validate(repo, dossier_id: str, user: CurrentUser) -> bool:
    """Validation réservée au relecteur (rôle global ou du dossier) et à l'administrateur."""
    return user.role in ("reviewer", "admin") or repo.member_role(dossier_id, user.id) == "reviewer"


def names(repo, user_ids) -> dict[str, str]:
    """{id: nom affiché} : l'interface montre des noms, jamais des identifiants."""
    from sqlalchemy import select

    from app.storage import schema as s

    ids = [i for i in set(user_ids) if i]
    if not ids:
        return {}
    with repo.engine.connect() as c:
        rows = c.execute(select(s.users.c.id, s.users.c.display_name).where(
            s.users.c.id.in_(ids))).all()
    return {r[0]: r[1] for r in rows}


# --- priorités -----------------------------------------------------------------------------------
def create_priority(repo, dossier_id: str, user: CurrentUser, *, title: str, description: str = "",
                    rank: int | None = None, status: str = "proposed",
                    source_ids: list[str] | None = None) -> Priority:
    if status != "proposed":
        raise GenerationError(422, "CREATE_AS_PROPOSED",
                              "Une priorité est créée « proposée » ; elle se valide par un relecteur")
    if rank is None:
        rank = max((p.rank for p in repo.list_priorities(dossier_id)), default=0) + 1
    p = repo.create_priority(
        dossier_id, title=title.strip(), description=description.strip(), rank=rank, status=status,
        source_ids=_check_sources(repo, dossier_id, source_ids or []), author_id=user.id)
    repo.audit(user.id, "priority.create", "priority", p.id, {"status": status, "rank": rank})
    return p


def patch_priority(repo, p: Priority, user: CurrentUser, changes: dict) -> Priority:
    """Rang, titre ou description modifiés : la validation tombe (« proposed »). Valider = `decide`."""
    values = {k: (v.strip() if isinstance(v, str) else v) for k, v in changes.items()
              if k in ("title", "description", "rank", "status") and v is not None}
    if values.get("status") not in (None, "proposed"):
        raise GenerationError(403, "VALIDATION_RESERVED",
                              "Valider ou rejeter est réservé à un relecteur (appel séparé)")
    if changes.get("source_ids") is not None:
        values["source_ids"] = _check_sources(repo, p.dossier_id, changes["source_ids"])
    changed = any(k in values and values[k] != getattr(p, k)
                  for k in ("title", "description", "rank", "source_ids"))
    if changed and p.status == "validated":
        values["status"] = "proposed"  # revalidation obligatoire
    if values.get("status") == "proposed":
        values.update(validated_by=None, validated_at=None)
    updated = repo.update_priority(p.id, **values)
    repo.audit(user.id, "priority.update", "priority", p.id,
               {k: v for k, v in values.items() if k not in ("source_ids", "validated_at")})
    return updated


def decide(repo, p: Priority, user: CurrentUser, status: str) -> Priority:
    """Valide ou rejette : relecteur ou administrateur ; le validateur et la date sont conservés."""
    if not can_validate(repo, p.dossier_id, user):
        raise GenerationError(403, "VALIDATION_RESERVED",
                              "Valider ou rejeter est réservé à un relecteur ou à un administrateur")
    if p.author_id == user.id and user.role != "admin":
        raise GenerationError(403, "SELF_VALIDATION",
                              "Quatre yeux : on ne valide pas une priorité qu'on a créée")
    from app.storage.schema import utcnow

    updated = repo.update_priority(p.id, status=status, validated_by=user.id,
                                   validated_at=utcnow())
    repo.audit(user.id, f"priority.{status}", "priority", p.id, {})
    return updated


# --- projets -------------------------------------------------------------------------------------
def _check_deps(repo, dossier_id: str, project_id: str | None, deps: list[str]) -> list[str]:
    deps = list(dict.fromkeys(deps))
    projects = {p.id: p for p in repo.list_projects(dossier_id)}
    for d in deps:
        if d not in projects or d == project_id:
            raise GenerationError(422, "BAD_DEPENDENCY", f"Dépendance invalide : {d}")
    if project_id is not None:  # pas de cycle entre projets
        graph = {i: list(p.depends_on) for i, p in projects.items()}
        stack, seen = list(deps), set()
        while stack:
            cur = stack.pop()
            if cur == project_id:
                raise GenerationError(422, "DEPENDENCY_CYCLE",
                                      "Cette dépendance créerait un cycle entre projets")
            if cur not in seen:
                seen.add(cur)
                stack.extend(graph.get(cur, []))
    return deps


def create_project(repo, dossier_id: str, user: CurrentUser, *, title: str, state: str = "existing",
                   duration_weeks: int | None = None, depends_on: list[str] | None = None,
                   source_ids: list[str] | None = None) -> ExistingProject:
    p = repo.create_project(
        dossier_id, title=title.strip(), state=state, duration_weeks=duration_weeks,
        depends_on=_check_deps(repo, dossier_id, None, depends_on or []),
        source_ids=_check_sources(repo, dossier_id, source_ids or []), author_id=user.id)
    repo.audit(user.id, "project.create", "project", p.id, {"state": state})
    return p


def patch_project(repo, p: ExistingProject, user: CurrentUser, changes: dict) -> ExistingProject:
    values = {k: (v.strip() if isinstance(v, str) else v) for k, v in changes.items()
              if k in ("title", "state", "duration_weeks") and (v is not None
                                                                 or k == "duration_weeks")}
    if changes.get("depends_on") is not None:
        values["depends_on"] = _check_deps(repo, p.dossier_id, p.id, changes["depends_on"])
    if changes.get("source_ids") is not None:
        values["source_ids"] = _check_sources(repo, p.dossier_id, changes["source_ids"])
    updated = repo.update_project(p.id, **values)
    repo.audit(user.id, "project.update", "project", p.id,
               {k: v for k, v in values.items() if k not in ("source_ids", "depends_on")})
    return updated
