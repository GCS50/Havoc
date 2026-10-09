"""Create the bootstrap admin user from ADMIN_* settings.

Idempotent: does nothing if a user with that email already exists.

    python -m scripts.seed_admin
"""

import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.models.enums import UserRole, UserStatus
from app.models.user import User


async def seed_admin() -> None:
    settings = get_settings()
    email = settings.admin_email.lower().strip()

    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(User).where(User.email == email))
        if existing is not None:
            print(f"[seed_admin] user {email!r} already exists (status={existing.status.value})")
            return

        db.add(
            User(
                email=email,
                password_hash=hash_password(settings.admin_password),
                name=settings.admin_name,
                status=UserStatus.active,
                role=UserRole.admin,
                project_id=settings.default_project_id,
            )
        )
        await db.commit()
        print(f"[seed_admin] created admin {email!r}")


async def _main() -> None:
    try:
        await seed_admin()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
