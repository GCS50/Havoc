# Havoc

#### Video Demo: https://www.youtube.com/watch?v=HMf0OXfk9pg
#### Description:

API-first platform for storing, versioning and serving structured data -
generic entities, attributes and auth. This repository is the first vertical
slice (and a CS50 final project):

- User registration with an **admin approval flow** and JWT auth
- A **generic entity mechanism** (`content` + immutable `content_versions` +
  an `entity_types` schema registry) with one concrete type: `certificate`
- A small REST API where an authenticated user can retrieve *their own*
  certificates - with **data-level** permission filtering (enforced in SQL,
  not in the response)
- A **web UI** served by the same app: employees sign in and see their
  certificates; admins approve registrations, issue and revoke certificates

Out of scope for this slice (but the data model leaves room for them): search,
multi-tenancy, webhooks, AI.

---

## Tech stack

| Concern | Choice |
|---|---|
| Language / framework | Python 3.12, FastAPI |
| ORM / migrations | SQLAlchemy 2.x (async, asyncpg) + Alembic |
| Database | PostgreSQL 16 |
| Validation | Pydantic v2 (I/O), JSON Schema (entity `data`) |
| Auth | JWT (PyJWT) for users; `api_keys` table stubbed for future service clients |
| Password hashing | bcrypt (SHA-256 pre-hash, no 72-byte limit) |
| Web UI | Plain HTML, CSS and JavaScript (no build step), served by FastAPI |
| Tests | pytest + httpx |

---

## Project layout

A detailed explanation of every file, a walkthrough of how a request flows
through the code, and the reasoning behind the main design decisions are in
**[FILES.md](FILES.md)**. The project plan (goals, skills, milestones) is in
**[GETTING_STARTED.md](GETTING_STARTED.md)**.

```
app/
  main.py              FastAPI app, exception handler, lifespan seeding
  core/
    config.py          Settings from environment / .env
    database.py        Async engine + session, get_db() dependency
    security.py        bcrypt hashing, JWT encode/decode
  models/              SQLAlchemy models (persistence only)
    base.py enums.py user.py api_key.py entity_type.py content.py
  schemas/             Pydantic request/response contracts
    auth.py user.py content.py
  api/
    deps.py            get_db, get_current_user, require_admin
    v1/
      router.py        aggregates the v1 routers
      auth.py          /v1/auth/register, /login, /me
      admin.py         /v1/admin/users, .../approve, .../suspend
      content.py       /v1/content ...
  services/            Business logic + ALL permission rules (testable, HTTP-free)
    auth_service.py user_service.py content_service.py
    schema_validation.py errors.py
  seeds/
    certificate_schema.py   single source of truth for the certificate JSON Schema
    runtime.py              startup: keep entity_types registry in sync
  web/                 Web UI (single-page app on top of /v1)
    index.html app.js styles.css
alembic/
  env.py
  versions/0001_initial.py   schema + enum types + certificate seed
scripts/
  seed_admin.py         create the bootstrap admin from ADMIN_* settings
tests/
  conftest.py           test DB bootstrap + per-test transaction rollback
  test_auth.py test_admin_approval.py test_content_visibility.py test_web_ui.py
```

### Architecture notes

- **Layering.** `api/` is thin HTTP glue: parse request → call a service →
  serialize a Pydantic response. Everything else - including every
  authorization and visibility decision - lives in `services/`, so it exists
  exactly once and is unit-testable without a web server. Models are
  persistence only; raw SQLAlchemy objects never leave the API.
- **Generic entities.** `content` is the stable handle for an entity.
  Every change appends a new `content_versions` row (JSONB `data`); existing
  version rows are never updated. `content.current_version_id` points at the
  row currently in effect. `entity_types` holds one JSON Schema per type;
  `certificate` is seeded, not special-cased in code (except the rule that
  only admins may issue one).
- **Data-level permissions.** `GET /v1/content` builds a query with
  `WHERE project_id = <user's project> AND data->>'issued_to' = <user id>`
  for non-admins. Non-admins literally cannot load rows that aren't theirs;
  admins get an unfiltered query.
- **Forward-compatibility.** `project_id` is a plain string (`"moon"`) that
  can become a FK to a future `projects` table. `api_keys` exists now,
  unused. Enums are native PostgreSQL types (extendable via `ALTER TYPE`).
  New entity types = new `entity_types` rows, no schema change.

---

## Data model

```
users(id, email⋆, password_hash, name,
      status[pending|active|suspended], role[employee|intern|admin],
      project_id, created_at, updated_at)

api_keys(id, key_hash, name, project_id, created_at, revoked_at?)

entity_types(id, name⋆, json_schema jsonb, created_at)

content(id, project_id, entity_type, slug,
        status[draft|published|revoked],
        current_version_id? → content_versions.id,
        created_at, updated_at,
        UNIQUE(project_id, entity_type, slug))

content_versions(id, content_id → content.id, data jsonb,
                 author_id → users.id, created_at)      -- append only
```

`certificate` `data` (JSON Schema, seeded in `entity_types`):

| field | type | required | notes |
|---|---|---|---|
| `type` | enum | ✓ | `certificate` \| `course_certificate` \| `award` \| `reference` \| `general_training` |
| `title` | string | ✓ | |
| `issued_to` | uuid | ✓ | user reference; drives visibility |
| `issued_by` | uuid | ✓ | user reference |
| `issue_date` | date | ✓ | |
| `valid_from` / `valid_until` | date | - | |
| `course_link` | uri | - | |
| `pdf_url` | string | - | |
| `verification_token` | string | ✓ | generated server-side on creation |

---

## Setup

Prerequisites: Docker + Docker Compose.

```bash
git clone <this repo> && cd Havoc
cp .env.example .env          # optional for compose; values below are baked in
docker compose up --build
```

That single command:

1. starts PostgreSQL 16 (`db`), waits until it is healthy;
2. builds the API image;
3. runs `alembic upgrade head` (creates the schema, seeds the `certificate`
   entity type);
4. runs `python -m scripts.seed_admin` (creates the admin from `ADMIN_*`);
5. starts Uvicorn on **http://localhost:8000**.

- Web UI: **http://localhost:8000/**
- Interactive OpenAPI docs: **http://localhost:8000/docs**
- Health check: `curl http://localhost:8000/health`

Default bootstrap admin (change via env / `.env`):
`admin@havoc.local` / `change-me-admin`

### Running things manually

```bash
docker compose exec api alembic upgrade head      # migrate
docker compose exec api alembic downgrade -1      # roll back one
docker compose exec api python -m scripts.seed_admin
```

### Configuration (`.env`)

| var | default | meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://havoc:havoc@db:5432/havoc` | SQLAlchemy async URL |
| `JWT_SECRET` | `dev-secret-...` | HMAC signing key - **set in production** |
| `JWT_ALGORITHM` | `HS256` | |
| `JWT_EXPIRY_MINUTES` | `60` | access-token lifetime |
| `DEFAULT_PROJECT_ID` | `moon` | project assigned to new users |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_NAME` | - | bootstrap admin |

### Tests

The suite needs a running PostgreSQL; it creates a `havoc_test` database and
applies the migrations to it, then rolls back each test in a transaction.

```bash
docker compose up -d db
docker compose run --rm api pytest -q
# or, with the stack already up:
docker compose exec api pytest -q
```

Covered: registration → `pending`; login blocked while `pending`; admin
approve/suspend flow; certificate visibility (user sees only their own, admin
sees all); only-admin issuance; schema validation; revoke keeps the row.

---

## Web UI

Open **http://localhost:8000/** in a browser. The UI is a single-page app in
`app/web/` that talks to the same `/v1` API as any other client, so every
permission rule is still enforced by the server.

- **Everyone:** register (the account starts as `pending`), sign in.
- **Employees:** see their own certificates as cards, open one for details,
  verification token and version history.
- **Admins:** see all certificates; approve, suspend or reactivate users on
  the *Users* page; issue a certificate to an active user via a form; revoke
  a certificate from its detail page.

---

## End-to-end example (curl)

```bash
BASE=http://localhost:8000/v1

# 1. An employee registers -> status "pending", cannot log in yet
curl -s -X POST $BASE/auth/register -H 'content-type: application/json' -d '{
  "email": "lorenz@geyser.at", "password": "hunter2hunter2", "name": "Lorenz Employee"
}'
# -> {"id":"<LORENZ_ID>", "status":"pending", "role":"employee", ...}

curl -s -X POST $BASE/auth/login -H 'content-type: application/json' -d '{
  "email": "lorenz@geyser.at", "password": "hunter2hunter2"
}'
# -> 401  "Account is not active (status: pending)"

# 2. Admin logs in
ADMIN_TOKEN=$(curl -s -X POST $BASE/auth/login -H 'content-type: application/json' -d '{
  "email": "admin@havoc.local", "password": "change-me-admin"
}' | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# 3. Admin lists pending users and approves Lorenz
curl -s $BASE/admin/users?status=pending -H "authorization: Bearer $ADMIN_TOKEN"
LORENZ_ID=...   # from step 1 / the list
curl -s -X POST $BASE/admin/users/$LORENZ_ID/approve -H "authorization: Bearer $ADMIN_TOKEN"
# -> {"status":"active", ...}

# 4. Lorenz can now log in
LORENZ_TOKEN=$(curl -s -X POST $BASE/auth/login -H 'content-type: application/json' -d '{
  "email": "lorenz@geyser.at", "password": "hunter2hunter2"
}' | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# 5. Admin issues a certificate to Lorenz
curl -s -X POST $BASE/content -H "authorization: Bearer $ADMIN_TOKEN" \
  -H 'content-type: application/json' -d '{
  "entity_type": "certificate",
  "data": {
    "type": "course_certificate",
    "title": "Course for the Moon Backend",
    "issued_to": "'"$LORENZ_ID"'",
    "issued_by": "'"$LORENZ_ID"'",
    "issue_date": "2026-09-01",
    "course_link": "https://learn.geyser.at/course"
  }
}'
# -> {"id":"<CERT_ID>", "status":"published",
#     "data":{..., "verification_token":"<generated>"}, "current_version_id":"..."}

# 6. Lorenz sees only his own certificates
curl -s "$BASE/content?entity_type=certificate" -H "authorization: Bearer $LORENZ_TOKEN"
# -> [ { ...the cert issued to Lorenz... } ]

curl -s $BASE/content/$CERT_ID -H "authorization: Bearer $LORENZ_TOKEN"          # 200
curl -s $BASE/content/$CERT_ID/versions -H "authorization: Bearer $LORENZ_TOKEN" # [ {v1} ]

# 7. Another employee cannot see it (403); admin can (200). Admin revokes:
curl -s -X POST $BASE/content/$CERT_ID/revoke -H "authorization: Bearer $ADMIN_TOKEN"
# -> {"status":"revoked", ...}   (row kept, not deleted)
```

## API summary

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /v1/auth/register` | - | Register; status `pending` |
| `POST /v1/auth/login` | - | JWT, only if status `active` |
| `GET /v1/auth/me` | user | Current user |
| `GET /v1/admin/users?status=` | admin | List users |
| `POST /v1/admin/users/{id}/approve` | admin | status → `active` |
| `POST /v1/admin/users/{id}/suspend` | admin | status → `suspended` |
| `GET /v1/content?entity_type=certificate` | user | Own certificates (all, if admin) |
| `POST /v1/content` | admin | Issue a certificate |
| `GET /v1/content/{id}` | user | One certificate (403 unless owner/admin) |
| `POST /v1/content/{id}/revoke` | admin | status → `revoked` |
| `GET /v1/content/{id}/versions` | user | Version history |
