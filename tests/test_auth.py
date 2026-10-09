"""Registration + login: pending status blocks login until approved."""

from sqlalchemy import select

from app.models.enums import UserStatus
from app.models.user import User

REGISTER = "/v1/auth/register"
LOGIN = "/v1/auth/login"


async def test_register_creates_pending_user(client, db_session):
    resp = await client.post(
        REGISTER,
        json={"email": "newbie@test.local", "password": "password123", "name": "Newbie"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["role"] == "employee"
    assert body["project_id"] == "moon"

    user = await db_session.scalar(select(User).where(User.email == "newbie@test.local"))
    assert user is not None
    assert user.status == UserStatus.pending


async def test_register_rejects_duplicate_email(client):
    payload = {"email": "dupe@test.local", "password": "password123", "name": "Dupe"}
    assert (await client.post(REGISTER, json=payload)).status_code == 201
    resp = await client.post(REGISTER, json=payload)
    assert resp.status_code == 409


async def test_login_fails_while_pending(client):
    await client.post(
        REGISTER,
        json={"email": "waiting@test.local", "password": "password123", "name": "Wait"},
    )
    resp = await client.post(
        LOGIN, json={"email": "waiting@test.local", "password": "password123"}
    )
    assert resp.status_code == 401


async def test_login_succeeds_once_active(client, db_session):
    await client.post(
        REGISTER,
        json={"email": "active@test.local", "password": "password123", "name": "Act"},
    )
    user = await db_session.scalar(select(User).where(User.email == "active@test.local"))
    user.status = UserStatus.active
    await db_session.commit()

    resp = await client.post(
        LOGIN, json={"email": "active@test.local", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_wrong_password(client, db_session):
    await client.post(
        REGISTER,
        json={"email": "pw@test.local", "password": "password123", "name": "Pw"},
    )
    user = await db_session.scalar(select(User).where(User.email == "pw@test.local"))
    user.status = UserStatus.active
    await db_session.commit()

    resp = await client.post(
        LOGIN, json={"email": "pw@test.local", "password": "wrong-password"}
    )
    assert resp.status_code == 401


async def test_local_domain_email_is_accepted(client):
    # Self-hosted installs use addresses like admin@havoc.local.
    resp = await client.post(
        REGISTER,
        json={"email": "someone@havoc.local", "password": "password123", "name": "Local"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "someone@havoc.local"
