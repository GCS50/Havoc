"""Admin-facing user management."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserStatus
from app.models.user import User
from app.services.errors import NotFoundError


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


async def list_users(
    db: AsyncSession, *, status: UserStatus | None = None
) -> list[User]:
    stmt = select(User).order_by(User.created_at)
    if status is not None:
        stmt = stmt.where(User.status == status)
    return list(await db.scalars(stmt))


async def set_user_status(
    db: AsyncSession, *, user_id: uuid.UUID, status: UserStatus
) -> User:
    user = await get_user(db, user_id)
    user.status = status
    await db.commit()
    await db.refresh(user)
    return user
