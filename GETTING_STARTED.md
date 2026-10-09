# Havoc - Getting Started

This is the planning document for my CS50x final project. It answers the
questions from the course's *Getting Started* section. How to install and run
the project is described in [README.md](README.md); every file is explained
in [FILES.md](FILES.md).

---

## What will the software do?

Organizations such as companies, clubs and schools hand out documents that
prove something about a person: course certificates, awards, references,
completed trainings. These usually end up as PDFs in email inboxes. Nobody can
find them later, there is no history of changes, and a third party has no way
to check whether a certificate is genuine or has been withdrawn.

**Havoc** is a self-hosted, API-first platform that stores this kind of
structured data centrally, versions every change and only shows each person
what they are allowed to see. The first use case is **certificates**:

- An administrator issues a certificate to a member.
- The member signs in and sees *their own* certificates, and nobody else's.
- Every certificate keeps its full version history and can be revoked, but
  never silently deleted.

Under the hood, certificates are not a special table. They are one
**entity type** in a generic model (`content` + `content_versions` + a JSON
Schema registry), so other kinds of data such as events or courses can be
added later without changing the database.

### Features

| Feature | Description |
|---|---|
| Registration with approval | New accounts start as `pending`; an admin must approve them before they can sign in. |
| JWT authentication | Login returns a signed token that authorizes every further request. |
| Roles | `employee`, `intern` and `admin`; admins manage users and certificates. |
| Certificates | Issue, list, view and revoke; data is validated against a JSON Schema. |
| Data-level permissions | Non-admins can only load their own certificates; the filter runs inside the SQL query. |
| Version history | Every change is a new, immutable version. |
| Web UI | Browser interface for members and admins, built on the same API. |
| REST API + docs | Every function is available over HTTP; interactive docs at `/docs`. |

### How will it be executed?

Havoc is a web application: a Python/FastAPI server with a PostgreSQL
database. It runs with a single `docker compose up --build`, either on a
laptop or, in my case, on a **Raspberry Pi 5** in my home network. Users open
the web UI in their browser; other programs can use the REST API directly.

---

## What new skills will I need?

CS50 introduced me to Python, SQL, HTTP and web development with Flask. For
this project I have to go further:

| Topic | What I need to learn |
|---|---|
| **FastAPI** | A modern Python web framework: routing, dependency injection, automatic OpenAPI docs. |
| **Async Python** | `async`/`await`, so the server does not block while waiting for the database. |
| **SQLAlchemy 2 (ORM)** | Mapping Python classes to tables instead of writing every SQL statement by hand. |
| **PostgreSQL** | Instead of SQLite: `JSONB` columns, native enum types, running as a server. |
| **Database migrations (Alembic)** | Changing the schema in a controlled, repeatable way. |
| **Authentication** | Password hashing with bcrypt, JSON Web Tokens, the difference between 401 and 403. |
| **Authorization** | Designing permission rules and enforcing them in the query, not just in the UI. |
| **JSON Schema** | Validating flexible, user-defined data structures. |
| **Automated testing** | pytest, test fixtures, isolating tests with transactions. |
| **Docker** | Packaging the app and database so it runs the same everywhere. |
| **Deployment** | Running the project on a Raspberry Pi (ARM64) in a local network. |
| **Plain JavaScript SPA** | Building a browser UI with `fetch`, hash routing and safe DOM rendering. |

Topics I have to research along the way: how to model versioned data, how to
avoid timing attacks at login, and how to keep a database schema and the code
in sync.

---

## Who will do what?

This is a **solo project**. I am responsible for the design, implementation,
testing, documentation and the video.

AI tools were used as helpers during development, as the course allows for
the final project. Files where AI assisted are marked in their comments.

---

## Outcomes

Most things take longer than expected, so I defined three levels of success
up front.

### Good outcome - a working backend
- [x] User registration with admin approval and JWT login
- [x] Generic data model with `certificate` as the first entity type
- [x] REST API: issue, list, view and revoke certificates
- [x] Users only ever see their own certificates (enforced in SQL)
- [x] Automated tests for authentication, approval and visibility
- [x] README with setup instructions

### Better outcome - usable by real people
- [x] Web UI for members and admins
- [x] One-command setup with Docker Compose
- [x] Running on a Raspberry Pi in my home network
- [x] Detailed documentation of every file and design decision
- [ ] Production settings: secret JWT key, changed admin password, database
      not exposed to the network

### Best outcome - a real platform
- [ ] Public verification page: anyone with a certificate's verification
      token can check whether it is valid or revoked, without an account
- [ ] Editing certificates through the API and UI (creating new versions)
- [ ] Entity types defined through the API, with per-type permission rules,
      so clubs can manage **events**, **courses** and more without code changes
- [ ] Multiple projects (organizations) with their own members and admins
- [ ] Forms and lists in the UI generated from each type's JSON Schema

---

## Milestones

| # | Milestone | Status |
|---|---|---|
| 1 | Data model, migrations and seed data | done |
| 2 | Registration, login, admin approval | done |
| 3 | Certificate API with permission filtering | done |
| 4 | Test suite | done |
| 5 | Docker setup and deployment on the Raspberry Pi | done |
| 6 | Web UI | done |
| 7 | Public certificate verification | open |
| 8 | README, video and submission | in progress |
