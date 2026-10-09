"""Registration and login logic."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.services.errors import AuthError, ConflictError

settings = get_settings()

# A valid bcrypt hash used to keep login timing uniform for unknown emails.
_TIMING_DUMMY_HASH = "$2b$12$cie6b9RO0vukU5gFsuese.uli7i.G9Zh5AmIzpxfREwntXR2QDf7m"


async def register_user(db: AsyncSession, *, email: str, password: str, name: str) -> User:
    email = email.lower().strip()
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ConflictError("Email is already registered")

    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
        status=UserStatus.pending,
        role=UserRole.employee,
        project_id=settings.default_project_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> User:
    email = email.lower().strip()
    user = await db.scalar(select(User).where(User.email == email))
    # Verify a hash even when the user is missing to keep timing uniform.
    if user is None:
        verify_password(password, _TIMING_DUMMY_HASH)
        raise AuthError("Invalid email or password")
    if not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password")
    if user.status != UserStatus.active:
        raise AuthError(f"Account is not active (status: {user.status.value})")
    return user
