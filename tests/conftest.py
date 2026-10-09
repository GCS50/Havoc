"""Test fixtures.

Requires a running PostgreSQL (the ``db`` service from docker-compose works).
A dedicated ``<dbname>_test`` database is created automatically and the full
Alembic migration chain is applied to it once per session. Each test runs
inside a transaction that is rolled back at the end, so tests never see each
other's data.

    # against the compose Postgres, from the host:
    DATABASE_URL=postgresql+asyncpg://havoc:havoc@localhost:5432/havoc pytest
"""

import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("JWT_SECRET", "test-secret-key")

_SOURCE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://havoc:havoc@localhost:5432/havoc"
)
_prefix, _dbname = _SOURCE_URL.rsplit("/", 1)
_dbname = _dbname.split("?")[0]
TEST_DB_NAME = f"{_dbname}_test"
TEST_DATABASE_URL = f"{_prefix}/{TEST_DB_NAME}"
MAINTENANCE_URL = f"{_prefix}/postgres"

# The app reads DATABASE_URL via app.core.config; point it at the test DB
# before anything from ``app`` is imported.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import UserRole, UserStatus  # noqa: E402
from app.models.user import User  # noqa: E402

get_settings.cache_clear()


async def _recreate_test_database() -> None:
    engine = create_async_engine(MAINTENANCE_URL, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :n AND pid <> pg_backend_pid()"
                ),
                {"n": TEST_DB_NAME},
            )
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
            await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _prepared_database():
    asyncio.run(_recreate_test_database())
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine(TEST_DATABASE_URL)
    conn = await engine.connect()
    trans = await conn.begin()
    session_factory = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _make_user(
    db: AsyncSession,
    *,
    email: str,
    role: UserRole = UserRole.employee,
    status: UserStatus = UserStatus.active,
    password: str = "password123",
    project_id: str = "moon",
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        name=email.split("@")[0].title(),
        role=role,
        status=status,
        project_id=project_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await _make_user(db_session, email="admin@test.local", role=UserRole.admin)


@pytest_asyncio.fixture
async def alice(db_session: AsyncSession) -> User:
    return await _make_user(db_session, email="alice@test.local")


@pytest_asyncio.fixture
async def bob(db_session: AsyncSession) -> User:
    return await _make_user(db_session, email="bob@test.local")


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role.value, "project_id": user.project_id},
    )
    return {"Authorization": f"Bearer {token}"}
