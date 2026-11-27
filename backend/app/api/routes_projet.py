"""Fiche projet (client, logo, demande, dates), recommandations des rapports d'audit, registre des entraînements."""

from fastapi import APIRouter, Request, UploadFile
from pydantic import BaseModel, Field

from app.api.routes_dossiers import not_found
from app.services import Repo, User, error_response, projet

router = APIRouter(tags=["projet"])
LOGO_ENVOI_MAX = 5 * 1024 * 1024  # fichier reçu ; il est ensuite réduit à ≈ 100 Ko


class ProfilePut(BaseModel):
    client_name: str | None = Field(default=None, min_length=1, max_length=255)
    client_request: str | None = Field(default=None, max_length=20000)
    request_summary: str | None = Field(default=None, max_length=200)
    start_date: str | None = None
    end_date: str | None = None
    clear_logo: bool = False


class RecommendationCreate(BaseModel):
    document_id: str
    title: str = Field(min_length=1, max_length=500)
    number: int | None = Field(default=None, ge=1, le=99)
    page: int | None = Field(default=None, ge=1)


class RecommendationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    number: int | None = Field(default=None, ge=1, le=99)
    page: int | None = Field(default=None, ge=1)
    status: str | None = None
    merge_into: str | None = None


class NoRecommendation(BaseModel):
    value: bool = True


def _membre(repo, dossier_id: str, user) -> bool:
    return repo.member_role(dossier_id, user.id) is not None


@router.get("/dossiers/{dossier_id}/profile")
def get_profile(dossier_id: str, repo: Repo, user: User):
    if not _membre(repo, dossier_id, user):
        return not_found("Dossier")
    return projet.get_profile(repo.engine, dossier_id)


@router.put("/dossiers/{dossier_id}/profile")
def put_profile(dossier_id: str, body: ProfilePut, repo: Repo, user: User):
    if not _membre(repo, dossier_id, user):
        return not_found("Dossier")
    champs = body.model_fields_set
    try:
        out = projet.save_profile(repo.engine, dossier_id, user.id, fields=champs,
                                  **body.model_dump(exclude={"clear_logo"}), clear_logo=body.clear_logo)
    except ValueError as exc:
        return error_response(422, "INVALID_PROFILE", str(exc))
    repo.audit(user.id, "profile.update", "dossier", dossier_id, {"fields": sorted(champs)})
    return out


@router.post("/dossiers/{dossier_id}/profile/logo")
async def upload_logo(dossier_id: str, file: UploadFile, request: Request, repo: Repo, user: User):
    if not _membre(repo, dossier_id, user):
        return not_found("Dossier")
    contenu = await file.read(LOGO_ENVOI_MAX + 1)
    if len(contenu) > LOGO_ENVOI_MAX:
        return error_response(413, "TOO_LARGE", "Image trop lourde (5 Mo au plus)")
    try:
        uri = projet.logo_data_uri(contenu)
    except ValueError as exc:
        return error_response(422, "INVALID_LOGO", str(exc))
    out = projet.save_profile(repo.engine, dossier_id, user.id, logo=uri, fields=set())
    repo.audit(user.id, "profile.logo", "dossier", dossier_id, {"bytes": len(uri)})
    return out


@router.get("/dossiers/{dossier_id}/recommendations")
def list_recommendations(dossier_id: str, repo: Repo, user: User):
    if not _membre(repo, dossier_id, user):
        return not_found("Dossier")
    return projet.overview(repo.engine, dossier_id)


@router.post("/dossiers/{dossier_id}/recommendations:extract")
def extract_recommendations(dossier_id: str, repo: Repo, user: User):
    if not _membre(repo, dossier_id, user):
        return not_found("Dossier")
    out = projet.extract(repo.engine, dossier_id, user.id)
    repo.audit(user.id, "recommendations.extract", "dossier", dossier_id, {"alerts": out["alerts"]})
    return out


@router.post("/dossiers/{dossier_id}/recommendations", status_code=201)
def add_recommendation(dossier_id: str, body: RecommendationCreate, repo: Repo, user: User):
    if not _membre(repo, dossier_id, user):
        return not_found("Dossier")
    try:
        out = projet.add_recommendation(repo.engine, dossier_id, user.id, **body.model_dump())
    except LookupError:
        return not_found("Rapport")
    repo.audit(user.id, "recommendation.add", "recommendation", out["id"], {})
    return out


@router.patch("/recommendations/{rec_id}")
def patch_recommendation(rec_id: str, body: RecommendationPatch, repo: Repo, user: User):
    rec = projet.get_recommendation(repo.engine, rec_id)
    if rec is None or not _membre(repo, rec.dossier_id, user):
        return not_found("Recommandation")
    champs = body.model_dump(exclude_unset=True)
    try:
        out = projet.patch_recommendation(repo.engine, rec, user.id, fields=champs)
    except ValueError as exc:
        return error_response(422, "INVALID_RECOMMENDATION", str(exc))
    repo.audit(user.id, "recommendation.update", "recommendation", rec_id, {"fields": sorted(champs)})
    return out


@router.put("/dossiers/{dossier_id}/reports/{document_id}/no-recommendation")
def no_recommendation(dossier_id: str, document_id: str, body: NoRecommendation, repo: Repo, user: User):
    if not _membre(repo, dossier_id, user):
        return not_found("Dossier")
    if document_id not in repo.document_roles(dossier_id):
        return not_found("Rapport")
    projet.confirm_no_recommendation(repo.engine, dossier_id, document_id, body.value)
    repo.audit(user.id, "report.no_recommendation", "document", document_id, {"value": body.value})
    return projet.overview(repo.engine, dossier_id)


@router.get("/trainings")
def list_trainings(repo: Repo, user: User):
    return projet.list_trainings(repo.engine)
