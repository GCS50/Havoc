"""Admin approval workflow."""

from tests.conftest import auth_headers

REGISTER = "/v1/auth/register"
LOGIN = "/v1/auth/login"


async def _register(client, email):
    resp = await client.post(
        REGISTER, json={"email": email, "password": "password123", "name": "T"}
    )
    return resp.json()["id"]


async def test_non_admin_cannot_list_users(client, alice):
    resp = await client.get("/v1/admin/users", headers=auth_headers(alice))
    assert resp.status_code == 403


async def test_admin_lists_pending_users(client, admin_user):
    await _register(client, "p1@test.local")
    resp = await client.get(
        "/v1/admin/users", params={"status": "pending"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert "p1@test.local" in emails


async def test_approve_flow_enables_login(client, admin_user):
    user_id = await _register(client, "approve-me@test.local")

    blocked = await client.post(
        LOGIN, json={"email": "approve-me@test.local", "password": "password123"}
    )
    assert blocked.status_code == 401

    approved = await client.post(
        f"/v1/admin/users/{user_id}/approve", headers=auth_headers(admin_user)
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "active"

    ok = await client.post(
        LOGIN, json={"email": "approve-me@test.local", "password": "password123"}
    )
    assert ok.status_code == 200


async def test_suspend_blocks_login(client, admin_user, alice):
    resp = await client.post(
        f"/v1/admin/users/{alice.id}/suspend", headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "suspended"

    login = await client.post(
        LOGIN, json={"email": "alice@test.local", "password": "password123"}
    )
    assert login.status_code == 401
