"""Tâches longues suivies en direct : lancer, suivre (étape, avancement, temps), arrêter."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.routes_dossiers import not_found
from app.services import Provider, Repo, User, findings, jobs, roadmap_service

router = APIRouter(tags=["jobs"])

LABELS = {"findings": "Extraction des constats", "roadmap": "Feuille de route"}


class JobStart(BaseModel):
    kind: Literal["findings", "roadmap"]


@router.post("/dossiers/{dossier_id}/jobs", status_code=202)
def start_job(dossier_id: str, body: JobStart, repo: Repo, provider: Provider, user: User):
    """Lance la tâche en arrière-plan et rend aussitôt son identifiant. Une seule tâche d'un même type
    par dossier : relancer pendant qu'elle tourne rend celle qui tourne (pas de doublon)."""
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    same = [j for j in jobs.running(dossier_id) if j.kind == body.kind]
    if same:
        return same[0].view()
    if body.kind == "findings":
        def fn():
            r = findings.extract(repo, provider, dossier_id, user)
            r["summary"] = (f"Terminé : {len(r['findings'])} nouveau(x) constat(s) ajouté(s), "
                            f"{len(r['rejected'])} écarté(s) faute de preuve retrouvée dans le texte")
            return r
    else:
        lang = repo.get_dossier(dossier_id)["language"]

        def fn():
            r = roadmap_service.generate(repo, provider, dossier_id, user, language=lang)
            n = len((r.get("roadmap") or {}).get("items", []))
            r["summary"] = f"Terminé : feuille de route créée ({n} initiatives). Ouverture…"
            return r
    return jobs.start(body.kind, dossier_id, LABELS[body.kind], fn).view()


@router.get("/dossiers/{dossier_id}/jobs")
def list_jobs(dossier_id: str, repo: Repo, user: User):
    if repo.member_role(dossier_id, user.id) is None:
        return not_found("Dossier")
    return [j.view(with_steps=False) for j in jobs.recent(dossier_id)]


@router.get("/jobs/busy")
def busy(user: User):
    """Ce qui occupe le modèle en ce moment (tous dossiers) : pour dire « en attente » au lieu de rien."""
    return [{"label": j.label, "dossier_id": j.dossier_id, "done": j.done_units, "total": j.total_units}
            for j in jobs.running()]


def _own(repo, user, job_id):
    j = jobs.get(job_id)
    return j if j and repo.member_role(j.dossier_id, user.id) is not None else None


@router.get("/jobs/{job_id}")
def get_job(job_id: str, repo: Repo, user: User):
    j = _own(repo, user, job_id)
    return j.view() if j else not_found("Tâche")


@router.post("/jobs/{job_id}:cancel")
def cancel_job(job_id: str, repo: Repo, user: User):
    j = _own(repo, user, job_id)
    if not j:
        return not_found("Tâche")
    jobs.cancel(job_id)
    return j.view()
