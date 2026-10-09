# Havoc - File-by-file guide

This document walks through every file in the repository: what it contains,
what it does, and why it is built the way it is. For a project overview,
setup instructions and the API summary, see [README.md](README.md).

Contents:

1. [How a request flows through the code](#1-how-a-request-flows-through-the-code)
2. [Top-level files](#2-top-level-files)
3. [`app/` - the application](#3-app--the-application)
4. [`alembic/` - database migrations](#4-alembic--database-migrations)
5. [`scripts/` - operational scripts](#5-scripts--operational-scripts)
6. [`tests/` - the test suite](#6-tests--the-test-suite)
7. [Design decisions](#7-design-decisions)

---

## 1. How a request flows through the code

Take `GET /v1/content` (an employee lists their certificates) as an example:

1. **`app/main.py`** receives the request; the FastAPI app has mounted all
   v1 routes under `/v1` via **`app/api/v1/router.py`**.
2. The route function `list_content` in **`app/api/v1/content.py`** declares
   two dependencies: `DbSession` and `CurrentUser` (both from
   **`app/api/deps.py`**).
3. `DbSession` opens a database session through `get_db()` in
   **`app/core/database.py`**.
4. `CurrentUser` reads the `Authorization: Bearer <token>` header, decodes the
   JWT with **`app/core/security.py`**, loads the `User` row
   (**`app/models/user.py`**) and rejects the request if the account is not
   `active`.
5. The route calls `content_service.list_certificates` in
   **`app/services/content_service.py`**. This is where the permission rule
   lives: for non-admins it adds `WHERE project_id = … AND
   data->>'issued_to' = <user id>` to the SQL query.
6. The rows (`Content` + its current `ContentVersion`, from
   **`app/models/content.py`**) are converted into `ContentResponse` objects
   (**`app/schemas/content.py`**) and returned as JSON.
7. If anything in the service raises a `ServiceError`
   (**`app/services/errors.py`**), the single exception handler in
   `app/main.py` turns it into a JSON error with the right status code.

Every endpoint follows this same shape: **route → dependencies → service →
schema**.

---

## 2. Top-level files

### `README.md`
Project title, video link, description, tech stack, data model, setup
instructions, an end-to-end `curl` walkthrough and the API summary.

### `FILES.md`
This file.

### `GETTING_STARTED.md`
The project plan: what Havoc does and why, the skills the project required,
and the good / better / best outcomes with their milestones.

### `pyproject.toml`
The Python package definition. It lists:
- **runtime dependencies**: FastAPI (web framework), Uvicorn (ASGI server),
  SQLAlchemy + asyncpg (async database access), Alembic (migrations),
  Pydantic + pydantic-settings (validation and configuration),
  email-validator, PyJWT (tokens), bcrypt (password hashing), jsonschema
  (validating entity data) and python-slugify (URL-friendly slugs);
- **dev dependencies** (`pip install ".[dev]"`): pytest, pytest-asyncio and
  httpx for the test suite;
- pytest settings (`asyncio_mode = "auto"` so every `async def test_…` runs
  without decorators) and a ruff line length.

Version ranges are pinned to a minor series so a fresh install behaves the
same as the one the project was developed against.

### `.env.example`
A template for the `.env` file that `app/core/config.py` reads. It contains
the database URL, JWT settings, the default project id and the credentials of
the bootstrap admin. Copy it to `.env` and adjust; when running without
Docker, the database host must be `localhost` instead of `db`.

### `Dockerfile`
Builds the API image: starts from `python:3.12-slim`, copies the project,
installs it with dev dependencies (so tests can run inside the container) and
starts Uvicorn on port 8000.

### `docker-compose.yml`
Defines two services:
- **`db`** - PostgreSQL 16 with a named volume for persistent data and a
  health check (`pg_isready`);
- **`api`** - built from the `Dockerfile`, waits until `db` is healthy, then
  runs `alembic upgrade head`, `python -m scripts.seed_admin` and finally
  Uvicorn. This makes `docker compose up --build` a one-command setup.

### `.dockerignore` / `.gitignore`
Keep virtual environments, caches, `.env` files and other local artefacts out
of the Docker build context and out of Git respectively.

### `alembic.ini`
Alembic's configuration: where the migration scripts live (`alembic/`) and
logging setup. It deliberately contains **no database URL** - that is
injected from the application settings in `alembic/env.py`, so there is only
one place where the URL is configured.

---

## 3. `app/` - the application

The application is split into layers. Each layer may only depend on the
layers below it:

```
api/        HTTP: routes, request parsing, auth dependencies
services/   business logic and every permission rule
models/     database tables (SQLAlchemy)
schemas/    API input/output shapes (Pydantic)
core/       configuration, database connection, security primitives
seeds/      built-in data (the certificate schema)
web/        the browser UI (static files, uses the API over HTTP)
```

### `app/main.py`
The entry point (`uvicorn app.main:app`). It:
- creates the `FastAPI` app with title, version and description (shown at
  `/docs`);
- defines a **lifespan** hook that runs `ensure_seed_entity_types()` on
  startup, so the certificate schema in the database always matches the code;
- installs **one exception handler** for `ServiceError`. Services raise
  plain Python exceptions such as `NotFoundError`; this handler maps them to
  HTTP responses (`{"detail": …}`, plus an `errors` list for schema
  validation failures);
- mounts all v1 routes under `/v1`;
- exposes `GET /health` for liveness checks;
- serves the web UI: `GET /` returns `app/web/index.html`, and everything
  under `/static/` is served from `app/web/`.

### `app/core/`

#### `config.py`
A `Settings` class built on `pydantic-settings`. Each field (e.g.
`database_url`, `jwt_secret`, `admin_email`) is read from an environment
variable of the same name or from `.env`, with a sensible development
default. `get_settings()` is wrapped in `lru_cache`, so the settings are
parsed once and shared everywhere.

#### `database.py`
Creates the **async SQLAlchemy engine** (`pool_pre_ping=True` to recover from
dropped connections) and a session factory. `get_db()` is a FastAPI
dependency that yields one session per request and rolls it back if the
request raises an exception. `expire_on_commit=False` lets route code keep
reading objects after a commit without extra queries.

#### `security.py`
All cryptography in one place:
- `hash_password` / `verify_password` - bcrypt. The password is first hashed
  with SHA-256 and base64-encoded (`_prehash`) because bcrypt silently ignores
  everything after byte 72; the pre-hash removes that limit.
  `verify_password` returns `False` instead of crashing on a malformed hash.
- `create_access_token` - builds a JWT with `sub` (user id), `iat`, `exp` and
  optional extra claims (the login route adds `role` and `project_id`).
- `decode_access_token` - verifies signature and expiry.

### `app/models/` - database tables

#### `base.py`
The SQLAlchemy `DeclarativeBase` plus two mixins reused by the models:
`UUIDMixin` (UUID primary key generated in Python) and `TimestampMixin`
(`created_at` / `updated_at`, filled by the database).

#### `enums.py`
The three enums shared by models and API schemas:
`UserStatus` (`pending`, `active`, `suspended`), `UserRole` (`employee`,
`intern`, `admin`) and `ContentStatus` (`draft`, `published`, `revoked`).
They subclass `str` so they serialize to plain strings in JSON.

#### `user.py`
The `users` table: unique email, password hash, name, status, role and
`project_id`. New users default to `pending` + `employee`. `project_id` is a
plain string (`"moon"`) for now so it can later become a foreign key to a
`projects` table without changing the API.

#### `api_key.py`
The `api_keys` table (hashed key, name, project, revocation time). It exists
for forward-compatibility - future machine-to-machine clients - but nothing
issues or checks API keys yet.

#### `entity_type.py`
The **schema registry**: one row per entity type (`name` is unique) holding a
JSON Schema in a `JSONB` column. Content data is validated against this
schema before it is stored.

#### `content.py`
The generic entity storage, split into two tables:
- **`Content`** - the stable handle: project, entity type, slug (unique per
  project and type), status and `current_version_id`.
- **`ContentVersion`** - an immutable snapshot of the entity's attributes
  (`data` as JSONB), who wrote it (`author_id`) and when.

`content` and `content_versions` reference each other (a version belongs to a
content row; a content row points at its current version). The
`use_alter=True` on that foreign key tells SQLAlchemy to add it after both
tables exist, which breaks the circular dependency.

#### `__init__.py`
Imports every model so that `Base.metadata` knows about all tables. Alembic
imports this package to see the complete schema.

### `app/schemas/` - API contracts

Pydantic models that describe exactly what the API accepts and returns.
Database objects never leave the API directly; they are always converted into
one of these, which prevents leaking fields like `password_hash`.

#### `__init__.py`
Allows email addresses on the `.local` domain (e.g. `admin@havoc.local`).
Pydantic's `EmailStr` uses the email-validator library, which rejects
special-use domains by default; for a self-hosted system on an internal
network `.local` addresses are normal, so the package removes `local` from
email-validator's list of reserved names. All other syntax checks still apply.

#### `auth.py`
`RegisterRequest` (valid email, password of 8–128 characters, name),
`LoginRequest` and `TokenResponse` (`access_token`, `token_type`,
`expires_in` seconds).

#### `user.py`
`UserResponse` - the public view of a user (no password hash).
`from_attributes=True` lets it be built straight from a `User` model.

#### `content.py`
`ContentCreateRequest` (entity type, optional slug, free-form `data` that is
validated later against the registry), `ContentResponse` (content metadata
merged with the current version's `data`) and `ContentVersionResponse` (one
entry of the version history).

### `app/api/` - HTTP layer

#### `deps.py`
Reusable FastAPI dependencies, exposed as typed aliases so route signatures
stay short:
- `DbSession` - a request-scoped database session;
- `CurrentUser` - decodes the bearer token, loads the user, returns **401**
  for a bad/expired token or unknown user and **403** if the account is not
  `active` (so a suspended user's old token stops working immediately);
- `AdminUser` - `CurrentUser` plus a check that the role is `admin`.

#### `v1/router.py`
Combines the `auth`, `admin` and `content` routers into one `api_router`,
which `main.py` mounts under `/v1`. Versioning the URL leaves room for a
future `/v2` without breaking clients.

#### `v1/auth.py`
- `POST /auth/register` - creates a `pending` user (201).
- `POST /auth/login` - checks credentials and status, returns a JWT.
- `GET /auth/me` - returns the logged-in user.

#### `v1/admin.py`
Admin-only user management:
- `GET /admin/users?status=` - list users, optionally filtered by status;
- `POST /admin/users/{id}/approve` - set status to `active`;
- `POST /admin/users/{id}/suspend` - set status to `suspended`.

#### `v1/content.py`
Certificate endpoints:
- `GET /content` - certificates visible to the caller;
- `POST /content` - issue a certificate (admin only);
- `GET /content/{id}` - one certificate (403 unless it was issued to you, or
  you are an admin);
- `POST /content/{id}/revoke` - mark as `revoked` (admin only; the row is
  kept);
- `GET /content/{id}/versions` - version history.

`_to_response` merges a `Content` row with its current version's `data` into
one `ContentResponse`.

The `__init__.py` files in `app/`, `app/api/`, `app/api/v1/`, `app/core/`,
`app/seeds/` and `app/services/` are empty; they only mark
the directories as Python packages.

### `app/services/` - business logic

All decisions about *who may do what* live here, not in the routes. Services
receive a database session and plain arguments, and raise domain exceptions
instead of HTTP errors, so they can be tested and reused without a web server.

#### `errors.py`
The exception hierarchy: `ServiceError` (400) with subclasses `AuthError`
(401), `PermissionDeniedError` (403), `NotFoundError` (404), `ConflictError`
(409) and `SchemaValidationError` (422, carries a list of field errors). The
status code is a class attribute, which the handler in `main.py` reads.

#### `auth_service.py`
- `register_user` - normalizes the email (lowercase, trimmed), rejects
  duplicates with `ConflictError`, hashes the password and stores the user as
  `pending` / `employee` in the default project.
- `authenticate_user` - looks up the user and verifies the password. If the
  email does not exist, it still verifies against a dummy bcrypt hash so the
  response takes the same time either way; otherwise an attacker could tell
  from the timing which emails are registered. Non-`active` accounts are
  rejected with a message that names the status.

#### `user_service.py`
`get_user`, `list_users` (optionally filtered by status, ordered by creation
time) and `set_user_status`, used by the admin endpoints.

#### `schema_validation.py`
`validate_entity_data` loads the JSON Schema for an entity type from the
`entity_types` table and validates a `data` dict with a Draft 2020-12
validator, including format checks (`uuid`, `date`, `uri`). All errors are
collected, sorted by field path and returned together, so a client can fix
every problem in one go.

#### `content_service.py`
The core of the project:
- `_can_view` - the single permission rule for one certificate: admins see
  everything; everyone else only sees certificates in their own project whose
  `issued_to` is their user id.
- `list_certificates` - applies the same rule **inside the SQL query**
  (`ContentVersion.data["issued_to"].astext == str(user.id)`), so rows that
  belong to others are never loaded at all.
- `get_certificate` / `list_versions` - load the entity and then check
  `_can_view`, returning 404 or 403 accordingly.
- `create_certificate` - only allows the `certificate` type, generates a
  random `verification_token` on the server, validates `data` against the
  registered schema, checks that `issued_to` is a real user, builds a slug
  from the title (adding a random suffix if it is taken), then creates the
  `Content` row, its first `ContentVersion` and links the two.
- `revoke_certificate` - sets the status to `revoked` without deleting
  anything, so the history is preserved.
- `get_certificate_row` - internal helper that re-reads a certificate
  without a permission check, used after create/revoke.

### `app/seeds/`

#### `certificate_schema.py`
The **single source of truth** for the certificate type: its name and its
JSON Schema. Required fields: `type` (one of five kinds), `title`,
`issued_to`, `issued_by`, `issue_date`, `verification_token`; optional:
`valid_from`, `valid_until`, `course_link`, `pdf_url`.
`additionalProperties: false` rejects unknown fields. Both the migration and
the startup check import this file, so the schema is never duplicated.

#### `runtime.py`
`ensure_seed_entity_types()` runs at application startup. For each built-in
type it inserts the registry row if it is missing, or updates it if the
schema in code has changed. That way a schema change in a new release takes
effect without a separate data migration.

### `app/web/` - the web UI

A single-page app written in plain HTML, CSS and JavaScript. There is no
framework and no build step, so the files in this folder are exactly what the
browser runs, and the Raspberry Pi / Docker image needs no Node.js.

The UI is just another API client: it logs in via `POST /v1/auth/login`,
keeps the JWT in `localStorage` and sends it as a bearer token. It never
decides *what* a user may see; it only renders what the API returns. Hiding
an admin button is a convenience, not a security measure - the server still
answers 403 if someone calls the endpoint anyway.

#### `index.html`
The page shell: the top bar (brand, navigation, current user, log-out
button), an empty `<main id="view">` that the script fills, and a toast area
for short success/error messages.

#### `app.js`
All UI logic, organized top to bottom:
- **Helpers** - `h()` builds DOM elements and always inserts text as text
  nodes, never as HTML, so a certificate title like `<script>` is displayed,
  not executed. `safeLink()` only turns `http(s)` URLs into links. Date
  helpers show dates in the browser's locale.
- **API client** - `api()` wraps `fetch`, adds the token, parses JSON and
  turns error responses into an `ApiError` with a readable message (including
  the field errors from schema validation). A 401 logs the user out.
- **Routing** - the URL hash selects a view (`#/login`, `#/register`, `#/`,
  `#/certificates/<id>`, `#/admin/users`, `#/admin/issue`). `route()`
  redirects logged-out users to the login page and non-admins away from
  admin pages, and ignores results of a view the user already left.
- **Views** - one function per page:
  - `loginView` / `registerView` - forms; after registering, the user is
    told that an admin has to approve the account;
  - `certificatesView` - cards for the user's certificates (all of them for
    admins, with the recipient's name);
  - `certificateView` - details, verification token, a revoked banner,
    the version history with each version's raw data, and (for admins) a
    *Revoke* button with a confirmation dialog;
  - `usersView` - admin page with pending registrations at the top and
    *Approve* / *Suspend* / *Reactivate* buttons;
  - `issueView` - admin form to issue a certificate to an active user; empty
    optional fields are left out of the request.

#### `styles.css`
The design: colors are CSS variables with a dark variant under
`prefers-color-scheme: dark`, cards and tables for content, status badges
(green = active/published, amber = pending, red = suspended/revoked), and a
small-screen layout below 640 px so the UI also works on a phone.

---

## 4. `alembic/` - database migrations

### `env.py`
Alembic's runtime script. It takes the database URL from
`app.core.config`, imports `app.models` so Alembic sees the full schema, and
runs migrations over an **async** engine (the project uses asyncpg
everywhere, so there is no second, synchronous driver). It supports both
online mode (against a live database) and offline mode (`--sql`, prints SQL).

### `script.py.mako`
The template Alembic uses when generating a new migration file with
`alembic revision`.

### `versions/0001_initial.py`
The first and only migration.
- `upgrade()` creates the three PostgreSQL enum types, then the tables
  `users`, `api_keys`, `entity_types`, `content` and `content_versions` with
  their indexes and constraints, adds the circular foreign key from
  `content.current_version_id` to `content_versions.id` last, and inserts
  the `certificate` row into `entity_types` using the schema from
  `app/seeds/certificate_schema.py`.
- `downgrade()` reverses everything in the opposite order.

The enums are created explicitly with `create_type=False` on the columns, so
`create_table` does not try to create them a second time.

---

## 5. `scripts/` - operational scripts

### `seed_admin.py`
Creates the first admin account from the `ADMIN_EMAIL`, `ADMIN_PASSWORD`
and `ADMIN_NAME` settings, directly as `active` + `admin`. This solves the
bootstrap problem: new registrations need an admin's approval, so someone
must exist to approve them. The script is idempotent - if the email already
exists it prints a message and does nothing, so it is safe to run on every
container start. Run it with `python -m scripts.seed_admin` from the project
root.

`scripts/__init__.py` is empty and makes `scripts` importable as a module.

---

## 6. `tests/` - the test suite

### `conftest.py`
Shared pytest fixtures:
- Before anything from `app` is imported, it rewrites `DATABASE_URL` to point
  at a separate `<dbname>_test` database, so tests never touch real data.
- `_prepared_database` (once per session) drops and recreates that database
  and runs all Alembic migrations on it - the tests exercise the real schema,
  not an approximation.
- `db_session` opens a connection, starts a transaction and hands out a
  session that uses savepoints. At the end of each test the outer transaction
  is rolled back, so every test starts with an empty database even though the
  code under test calls `commit()`.
- `client` is an httpx `AsyncClient` talking to the FastAPI app in-process,
  with `get_db` overridden to use the test session.
- `admin_user`, `alice` and `bob` create ready-to-use active users;
  `auth_headers(user)` builds a valid `Authorization` header for one.

### `test_auth.py`
Registration creates a `pending` employee in project `moon`; duplicate
emails are rejected (409); login fails while `pending`, succeeds once
`active`, and fails with a wrong password; `.local` email addresses are
accepted.

### `test_admin_approval.py`
Non-admins cannot list users (403); an admin sees pending registrations;
approving a user makes login work; suspending a user blocks login.

### `test_content_visibility.py`
Only admins can issue certificates; issuing generates a verification token
and exactly one version; a user sees only their own certificates and another
user sees none; admins see all; fetching someone else's certificate returns
403; revoking is admin-only, sets `revoked` and keeps the row; data that
violates the schema is rejected with 422.

### `test_web_ui.py`
The root URL returns the HTML page, and the JavaScript and CSS files are
served under `/static/`.

`tests/__init__.py` is empty; it lets the test modules import helpers from
`tests.conftest`.

---

## 7. Design decisions

**Generic entities instead of a `certificates` table.** A dedicated table
would have been simpler for one type. But the goal of Havoc is a platform
for *any* structured data, so certificates are stored as generic `content`
with a JSON Schema in `entity_types`. Adding a new type (e.g. "equipment
loan") means inserting a schema row - no new table, no migration, no new
endpoint logic. The trade-off is that the database cannot enforce
certificate-specific constraints; the JSON Schema validation in the service
layer takes over that job.

**Append-only versions.** Updating a certificate in place would lose its
history. Instead every change writes a new `content_versions` row and moves
`current_version_id`. This gives an audit trail for free, which matters for
documents like certificates where "what did it say on date X?" is a real
question.

**Revoke, never delete.** A revoked certificate stays in the database with
status `revoked`. A certificate that simply disappears cannot be told apart
from one that never existed; keeping the row makes revocation verifiable.

**Permissions in SQL, not in Python.** The list endpoint filters with a
`WHERE` clause instead of loading everything and filtering the result. That
is faster, and more importantly it means a bug in the response code cannot
leak other people's data, because that data is never loaded.

**Services separate from routes.** Routes only translate between HTTP and
Python. Keeping all rules in `services/` means each rule is written exactly
once and the permission logic can be read in one file.

**Admin approval for new accounts.** The system holds personal documents of
an organization's members, so open self-registration alone would let anyone
in. Registration therefore creates a `pending` account that an admin must
approve; the `seed_admin` script provides the first admin.

**Async throughout.** FastAPI, SQLAlchemy (asyncpg) and even Alembic run
asynchronously, so the server does not block while waiting on the database
and only one database driver is needed.

**The web UI is just another API client.** The UI could have been built
with server-rendered templates, but then the browser would get its data a
different way than every other client. Building it on top of the public
`/v1` API keeps Havoc API-first: anything the UI can do, a script can do too,
and the permission rules exist only once, on the server. Plain JavaScript
instead of a framework like React keeps the project free of a JavaScript
build toolchain, which matters for deploying on a Raspberry Pi.

**Real PostgreSQL in tests.** The tests run against PostgreSQL with the real
migrations instead of SQLite, because the code depends on PostgreSQL features
(JSONB queries, native enums). Per-test rollbacks keep them isolated and fast.
