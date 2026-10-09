"""Content endpoints (certificates in this slice)."""

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models.content import Content, ContentVersion
from app.schemas.content import ContentCreateRequest, ContentResponse, ContentVersionResponse
from app.services import content_service

router = APIRouter(prefix="/content", tags=["content"])

_CERTIFICATE = "certificate"


def _to_response(content: Content, version: ContentVersion | None) -> ContentResponse:
    return ContentResponse(
        id=content.id,
        project_id=content.project_id,
        entity_type=content.entity_type,
        slug=content.slug,
        status=content.status,
        current_version_id=content.current_version_id,
        created_at=content.created_at,
        updated_at=content.updated_at,
        data=version.data if version is not None else None,
    )


@router.get(
    "",
    response_model=list[ContentResponse],
    summary="List certificates visible to the current user",
)
async def list_content(
    db: DbSession,
    user: CurrentUser,
    entity_type: str = Query(default=_CERTIFICATE),
) -> list[ContentResponse]:
    if entity_type != _CERTIFICATE:
        return []
    rows = await content_service.list_certificates(db, user=user)
    return [_to_response(content, version) for content, version in rows]


@router.post(
    "",
    response_model=ContentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a certificate (admin only)",
)
async def create_content(
    payload: ContentCreateRequest, db: DbSession, admin: AdminUser
) -> ContentResponse:
    content, version = await content_service.create_certificate(
        db,
        author=admin,
        entity_type=payload.entity_type,
        slug=payload.slug,
        data=payload.data,
    )
    return _to_response(content, version)


@router.get(
    "/{content_id}",
    response_model=ContentResponse,
    summary="Get one certificate (403 unless issued_to == you, or admin)",
)
async def get_content(
    content_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> ContentResponse:
    content, version = await content_service.get_certificate(
        db, user=user, content_id=content_id
    )
    return _to_response(content, version)


@router.post(
    "/{content_id}/revoke",
    response_model=ContentResponse,
    summary="Revoke a certificate (admin only, no delete)",
)
async def revoke_content(
    content_id: uuid.UUID, db: DbSession, admin: AdminUser
) -> ContentResponse:
    content, version = await content_service.revoke_certificate(db, content_id=content_id)
    return _to_response(content, version)


@router.get(
    "/{content_id}/versions",
    response_model=list[ContentVersionResponse],
    summary="Version history of a certificate",
)
async def list_content_versions(
    content_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[ContentVersionResponse]:
    versions = await content_service.list_versions(db, user=user, content_id=content_id)
    return [ContentVersionResponse.model_validate(v) for v in versions]
