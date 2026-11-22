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
    return ids


# --- priorités -----------------------------------------------------------------------------------
def create_priority(repo, dossier_id: str, user: CurrentUser, *, title: str, description: str = "",
                    rank: int | None = None, status: str = "proposed",
                    source_ids: list[str] | None = None) -> Priority:
    if rank is None:
        rank = max((p.rank for p in repo.list_priorities(dossier_id)), default=0) + 1
    p = repo.create_priority(
        dossier_id, title=title.strip(), description=description.strip(), rank=rank, status=status,
        source_ids=_check_sources(repo, dossier_id, source_ids or []), author_id=user.id)
    repo.audit(user.id, "priority.create", "priority", p.id, {"status": status, "rank": rank})
    return p


def patch_priority(repo, p: Priority, user: CurrentUser, changes: dict) -> Priority:
    """Un titre ou une description modifiés repassent « proposed » : il faut revalider."""
    values = {k: (v.strip() if isinstance(v, str) else v) for k, v in changes.items()
              if k in ("title", "description", "rank", "status") and v is not None}
    if changes.get("source_ids") is not None:
        values["source_ids"] = _check_sources(repo, p.dossier_id, changes["source_ids"])
    if ("title" in values or "description" in values) and "status" not in values \
            and p.status == "validated":
        values["status"] = "proposed"
    updated = repo.update_priority(p.id, **values)
    repo.audit(user.id, "priority.update", "priority", p.id,
               {k: v for k, v in values.items() if k != "source_ids"})
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
