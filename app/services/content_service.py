"""Content (generic entity) logic, including all data-level permission rules.

Visibility is enforced in the SQL query, not by filtering response objects:
a non-admin user only ever loads certificates issued to them, within their
own project.
"""

import uuid
from typing import Any

from slugify import slugify
from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content, ContentVersion
from app.models.enums import ContentStatus, UserRole
from app.models.user import User
from app.services.errors import NotFoundError, PermissionDeniedError, SchemaValidationError
from app.services.schema_validation import validate_entity_data

CERTIFICATE = "certificate"

ContentRow = Row[tuple[Content, ContentVersion]]


def _make_slug(title: str) -> str:
    base = slugify(title)[:200] or "certificate"
    return base


def _can_view(user: User, content: Content, version: ContentVersion | None) -> bool:
    if user.role == UserRole.admin:
        return True
    if version is None:
        return False
    return (
        content.project_id == user.project_id
        and str(version.data.get("issued_to")) == str(user.id)
    )


def _select_content_with_current_version():
    return select(Content, ContentVersion).join(
        ContentVersion, Content.current_version_id == ContentVersion.id
    )


async def list_certificates(db: AsyncSession, *, user: User) -> list[ContentRow]:
    stmt = (
        _select_content_with_current_version()
        .where(Content.entity_type == CERTIFICATE)
        .order_by(Content.created_at.desc())
    )
    if user.role != UserRole.admin:
        stmt = stmt.where(
            Content.project_id == user.project_id,
            ContentVersion.data["issued_to"].astext == str(user.id),
        )
    result = await db.execute(stmt)
    return list(result.all())


async def get_certificate(
    db: AsyncSession, *, user: User, content_id: uuid.UUID
) -> ContentRow:
    result = await db.execute(
        _select_content_with_current_version().where(
            Content.id == content_id, Content.entity_type == CERTIFICATE
        )
    )
    row = result.first()
    if row is None:
        raise NotFoundError("Certificate not found")
    content, version = row
    if not _can_view(user, content, version):
        raise PermissionDeniedError("You cannot access this certificate")
    return row


async def list_versions(
    db: AsyncSession, *, user: User, content_id: uuid.UUID
) -> list[ContentVersion]:
    content = await db.get(Content, content_id)
    if content is None or content.entity_type != CERTIFICATE:
        raise NotFoundError("Certificate not found")

    versions = list(
        await db.scalars(
            select(ContentVersion)
            .where(ContentVersion.content_id == content_id)
            .order_by(ContentVersion.created_at)
        )
    )
    current = next(
        (v for v in versions if v.id == content.current_version_id),
        versions[-1] if versions else None,
    )
    if not _can_view(user, content, current):
        raise PermissionDeniedError("You cannot access this certificate")
    return versions


async def create_certificate(
    db: AsyncSession,
    *,
    author: User,
    entity_type: str,
    slug: str | None,
    data: dict[str, Any],
) -> ContentRow:
    if entity_type != CERTIFICATE:
        raise PermissionDeniedError(
            f"Only '{CERTIFICATE}' entities can be created in this slice"
        )

    data = dict(data)
    # Server-generated, immutable identifier for public verification.
    data["verification_token"] = uuid.uuid4().hex

    await validate_entity_data(db, entity_type=entity_type, data=data)

    # issued_to must reference a real user (visibility depends on it).
    issued_to = uuid.UUID(str(data["issued_to"]))
    if await db.get(User, issued_to) is None:
        raise SchemaValidationError(
            "issued_to does not reference an existing user",
            errors=["issued_to: no such user"],
        )

    project_id = author.project_id
    slug = (slug or _make_slug(str(data["title"]))).strip()
    slug_taken = await db.scalar(
        select(Content.id).where(
            Content.project_id == project_id,
            Content.entity_type == entity_type,
            Content.slug == slug,
        )
    )
    if slug_taken is not None:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    content = Content(
        project_id=project_id,
        entity_type=entity_type,
        slug=slug,
        status=ContentStatus.published,
    )
    db.add(content)
    await db.flush()

    version = ContentVersion(content_id=content.id, data=data, author_id=author.id)
    db.add(version)
    await db.flush()

    content.current_version_id = version.id
    await db.commit()

    return await get_certificate_row(db, content_id=content.id)


async def revoke_certificate(
    db: AsyncSession, *, content_id: uuid.UUID
) -> ContentRow:
    content = await db.get(Content, content_id)
    if content is None or content.entity_type != CERTIFICATE:
        raise NotFoundError("Certificate not found")
    content.status = ContentStatus.revoked
    await db.commit()
    return await get_certificate_row(db, content_id=content_id)


async def get_certificate_row(db: AsyncSession, *, content_id: uuid.UUID) -> ContentRow:
    """Fetch (Content, current ContentVersion) without a permission check."""
    result = await db.execute(
        _select_content_with_current_version().where(Content.id == content_id)
    )
    row = result.first()
    if row is None:
        raise NotFoundError("Certificate not found")
    return row
