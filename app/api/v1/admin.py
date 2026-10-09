"""Admin endpoints: user approval workflow."""

import uuid

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, DbSession
from app.models.enums import UserStatus
from app.schemas.user import UserResponse
from app.services import user_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse], summary="List users (optionally by status)")
async def list_users(
    db: DbSession,
    _: AdminUser,
    status: UserStatus | None = Query(default=None),
) -> list[UserResponse]:
    users = await user_service.list_users(db, status=status)
    return [UserResponse.model_validate(u) for u in users]


@router.post(
    "/users/{user_id}/approve",
    response_model=UserResponse,
    summary="Approve a pending user (status -> active)",
)
async def approve_user(user_id: uuid.UUID, db: DbSession, _: AdminUser) -> UserResponse:
    user = await user_service.set_user_status(db, user_id=user_id, status=UserStatus.active)
    return UserResponse.model_validate(user)


@router.post(
    "/users/{user_id}/suspend",
    response_model=UserResponse,
    summary="Suspend a user (status -> suspended)",
)
async def suspend_user(user_id: uuid.UUID, db: DbSession, _: AdminUser) -> UserResponse:
    user = await user_service.set_user_status(db, user_id=user_id, status=UserStatus.suspended)
    return UserResponse.model_validate(user)
