"""Jetons de session opaques : le jeton n'est jamais stocké, seulement son SHA-256."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, insert, select

from app.storage import schema as s


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def create_session(engine, user_id: str, ttl_hours: int, now: datetime | None = None) -> str:
    """Crée une session et renvoie le jeton en clair (affiché une seule fois)."""
    token = secrets.token_urlsafe(32)
    now = now or datetime.now(UTC)
    with engine.begin() as c:
        c.execute(insert(s.sessions).values(
            token_hash=hash_token(token), user_id=user_id,
            expires_at=now + timedelta(hours=ttl_hours)))
    return token


def user_for_token(engine, token: str, now: datetime | None = None) -> dict | None:
    """Utilisateur actif associé à un jeton valide et non expiré, sinon None."""
    now = now or datetime.now(UTC)
    with engine.connect() as c:
        row = c.execute(
            select(s.users.c.id, s.users.c.role, s.users.c.active, s.sessions.c.expires_at)
            .join(s.sessions, s.sessions.c.user_id == s.users.c.id)
            .where(s.sessions.c.token_hash == hash_token(token))).first()
    if row is None or not row.active or _aware(row.expires_at) <= now:
        return None
    return {"id": row.id, "role": row.role}


def revoke(engine, token: str) -> None:
    with engine.begin() as c:
        c.execute(delete(s.sessions).where(s.sessions.c.token_hash == hash_token(token)))
