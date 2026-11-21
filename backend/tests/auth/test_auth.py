# ruff: noqa: F811
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth import tokens
from app.auth.passwords import hash_password, verify_password
from app.storage import schema as s
from tests.workflow.world import PASSWORD, world  # noqa: F401


def test_passwords_hash_and_verify():
    h = hash_password("secret")
    assert h != "secret" and "secret" not in h
    assert verify_password(h, "secret") and not verify_password(h, "autre")
    assert not verify_password("pas-un-hash", "secret")


def test_password_never_stored_in_clear(world):
    with world.repo.engine.connect() as c:
        hashes = [r[0] for r in c.execute(select(s.users.c.password_hash))]
    assert hashes and all(PASSWORD not in h and h.startswith("$argon2") for h in hashes)


def test_token_stored_hashed_only(world):
    token = world.h_alice["Authorization"].split()[1]
    with world.repo.engine.connect() as c:
        stored = [r[0] for r in c.execute(select(s.sessions.c.token_hash))]
    assert token not in stored and tokens.hash_token(token) in stored


def test_401_without_or_with_bad_token(world):
    assert world.client.get("/api/v1/auth/me").status_code == 401
    assert world.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nope"}
                            ).status_code == 401
    assert world.client.get("/api/v1/dossiers").status_code == 401


def test_login_me_logout(world):
    me = world.client.get("/api/v1/auth/me", headers=world.h_bob).json()
    assert me == {"id": world.bob, "role": "reviewer"}
    assert world.client.post("/api/v1/auth/logout", headers=world.h_bob).status_code == 204
    assert world.client.get("/api/v1/auth/me", headers=world.h_bob).status_code == 401


def test_bad_credentials_audited(world):
    r = world.client.post("/api/v1/auth/login", json={"email": "alice@ex.test", "password": "x"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "BAD_CREDENTIALS"
    r = world.client.post("/api/v1/auth/login", json={"email": "nobody@ex.test", "password": "x"})
    assert r.status_code == 401


def test_expired_token_refused(world):
    token = tokens.create_session(world.repo.engine, world.alice, 1,
                                  now=datetime.now(UTC) - timedelta(hours=2))
    assert tokens.user_for_token(world.repo.engine, token) is None
    r = world.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_dev_mode_still_works(client):
    """La fixture globale « client » force auth_mode=dev : les autres lots en dépendent."""
    assert client.get("/api/v1/auth/me").json() == {"id": "usr_dev", "role": "admin"}
