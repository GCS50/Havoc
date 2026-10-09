"""Certificate visibility: users see only their own, admins see all."""

from tests.conftest import auth_headers

CONTENT = "/v1/content"


def _cert_payload(issued_to, issued_by, title="Python Basics"):
    return {
        "entity_type": "certificate",
        "data": {
            "type": "course_certificate",
            "title": title,
            "issued_to": str(issued_to),
            "issued_by": str(issued_by),
            "issue_date": "2026-01-15",
        },
    }


async def _issue(client, admin_user, issued_to, **kw):
    resp = await client.post(
        CONTENT,
        json=_cert_payload(issued_to.id, admin_user.id, **kw),
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_only_admin_can_issue(client, admin_user, alice):
    resp = await client.post(
        CONTENT, json=_cert_payload(alice.id, admin_user.id), headers=auth_headers(alice)
    )
    assert resp.status_code == 403


async def test_issue_generates_verification_token_and_version(client, admin_user, alice):
    cert = await _issue(client, admin_user, alice)
    assert cert["status"] == "published"
    assert cert["data"]["verification_token"]
    assert cert["current_version_id"]

    versions = await client.get(
        f"{CONTENT}/{cert['id']}/versions", headers=auth_headers(admin_user)
    )
    assert versions.status_code == 200
    assert len(versions.json()) == 1


async def test_user_sees_only_own_certificates(client, admin_user, alice, bob):
    await _issue(client, admin_user, alice, title="Alice Cert")

    alice_list = await client.get(
        CONTENT, params={"entity_type": "certificate"}, headers=auth_headers(alice)
    )
    assert alice_list.status_code == 200
    assert [c["data"]["issued_to"] for c in alice_list.json()] == [str(alice.id)]

    bob_list = await client.get(
        CONTENT, params={"entity_type": "certificate"}, headers=auth_headers(bob)
    )
    assert bob_list.status_code == 200
    assert bob_list.json() == []


async def test_admin_sees_all_certificates(client, admin_user, alice, bob):
    await _issue(client, admin_user, alice, title="A")
    await _issue(client, admin_user, bob, title="B")

    resp = await client.get(
        CONTENT, params={"entity_type": "certificate"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_get_other_users_certificate_is_forbidden(client, admin_user, alice, bob):
    cert = await _issue(client, admin_user, alice)

    assert (
        await client.get(f"{CONTENT}/{cert['id']}", headers=auth_headers(alice))
    ).status_code == 200
    assert (
        await client.get(f"{CONTENT}/{cert['id']}", headers=auth_headers(bob))
    ).status_code == 403
    assert (
        await client.get(f"{CONTENT}/{cert['id']}", headers=auth_headers(admin_user))
    ).status_code == 200


async def test_revoke_sets_status_and_keeps_row(client, admin_user, alice):
    cert = await _issue(client, admin_user, alice)

    forbidden = await client.post(
        f"{CONTENT}/{cert['id']}/revoke", headers=auth_headers(alice)
    )
    assert forbidden.status_code == 403

    revoked = await client.post(
        f"{CONTENT}/{cert['id']}/revoke", headers=auth_headers(admin_user)
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    still_there = await client.get(
        f"{CONTENT}/{cert['id']}", headers=auth_headers(admin_user)
    )
    assert still_there.status_code == 200


async def test_invalid_certificate_data_is_rejected(client, admin_user, alice):
    resp = await client.post(
        CONTENT,
        json={
            "entity_type": "certificate",
            "data": {"type": "certificate", "title": "No recipient"},
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 422
