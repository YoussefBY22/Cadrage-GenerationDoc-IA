"""Export d'un livrable approuvé : POST /deliverables/{id}/exports."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.routes_dossiers import not_found
from app.config import get_settings
from app.export.common import ExportForbidden, ExportUnavailable, export_deliverable
from app.services import Repo, User, error_response
from app.storage import schema as s

router = APIRouter(tags=["export"])

MEDIA = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
}


class ExportRequest(BaseModel):
    format: str = "docx"


def _dossier_of(repo, deliverable_id: str) -> str | None:
    from sqlalchemy import select

    with repo.engine.connect() as c:
        return c.execute(
            select(s.deliverables.c.dossier_id).where(s.deliverables.c.id == deliverable_id)
        ).scalar()


@router.post("/deliverables/{deliverable_id}/exports")
def create_export(deliverable_id: str, body: ExportRequest, repo: Repo, user: User):
    dossier_id = _dossier_of(repo, deliverable_id)
    if dossier_id is None or repo.member_role(dossier_id, user.id) is None:
        return not_found("Livrable")
    if body.format not in MEDIA:
        return error_response(422, "INVALID_FORMAT", "Format attendu : docx, pptx ou pdf")
    out_dir = Path(get_settings().upload_dir).parent / "exports"
    try:
        path, digest = export_deliverable(repo, deliverable_id, body.format, user.id, out_dir)
    except ExportForbidden as exc:
        return error_response(403, "EXPORT_FORBIDDEN", str(exc))
    except ExportUnavailable as exc:
        return error_response(501, "EXPORT_UNAVAILABLE", str(exc))
    return FileResponse(path, media_type=MEDIA[body.format], filename=path.name,
                        headers={"X-Content-SHA256": digest})
