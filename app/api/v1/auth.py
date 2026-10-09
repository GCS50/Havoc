"""Auth endpoints: registration and login."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account (starts in 'pending', needs admin approval)",
)
async def register(payload: RegisterRequest, db: DbSession) -> UserResponse:
    user = await auth_service.register_user(
        db, email=payload.email, password=payload.password, name=payload.name
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse, summary="Exchange credentials for a JWT")
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = await auth_service.authenticate_user(
        db, email=payload.email, password=payload.password
    )
    token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role.value, "project_id": user.project_id},
    )
    return TokenResponse(
        access_token=token, expires_in=settings.jwt_expiry_minutes * 60
    )


@router.get("/me", response_model=UserResponse, summary="The current authenticated user")
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
