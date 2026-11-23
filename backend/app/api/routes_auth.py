"""Connexion, déconnexion, utilisateur courant, ajout de membres à un dossier."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.deps import bearer_token
from app.auth import tokens
from app.auth.passwords import verify_password
from app.config import get_settings
from app.services import Repo, User, error_response

router = APIRouter(tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class MemberIn(BaseModel):
    user_id: str
    role: Literal["consultant", "reviewer", "admin"] = "consultant"


@router.post("/auth/login")
def login(body: LoginIn, repo: Repo):
    user = repo.get_user_by_email(body.email)
    ok = bool(user and user.get("active", True)
              and verify_password(user["password_hash"], body.password))
    if not ok:
        repo.audit(None, "auth.login_failed", "user", "-", {})
        return error_response(401, "BAD_CREDENTIALS", "Identifiants invalides")
    token = tokens.create_session(repo.engine, user["id"], get_settings().session_ttl_hours)
    repo.audit(user["id"], "auth.login", "user", user["id"], {})
    return {"token": token, "user": {"id": user["id"], "role": user["role"]}}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, repo: Repo, user: User):
    token = bearer_token(request)
    if token:
        tokens.revoke(repo.engine, token)
    repo.audit(user.id, "auth.logout", "user", user.id, {})


@router.get("/auth/me")
def me(user: User):
    return {"id": user.id, "role": user.role}


@router.post("/dossiers/{dossier_id}/members", status_code=201)
def add_member(dossier_id: str, body: MemberIn, repo: Repo, user: User):
    dossier = repo.get_dossier(dossier_id)
    if dossier is None or repo.member_role(dossier_id, user.id) is None:
        return error_response(404, "NOT_FOUND", "Dossier introuvable")
    if user.role != "admin" and dossier["owner_id"] != user.id:
        return error_response(403, "FORBIDDEN_ROLE", "Réservé à l'administrateur ou au propriétaire")
    if body.role in ("reviewer", "admin") and body.user_id == user.id and user.role != "admin":
        return error_response(403, "SELF_REVIEWER",
                              "On ne peut pas se nommer relecteur ni administrateur de son propre dossier")
    repo.add_member(dossier_id, body.user_id, body.role)
    repo.audit(user.id, "member.add", "dossier", dossier_id,
               {"user_id": body.user_id, "role": body.role})
    return {"dossier_id": dossier_id, "user_id": body.user_id, "role": body.role}
