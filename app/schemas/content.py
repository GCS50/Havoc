"""Request/response schemas for the generic content endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ContentStatus


class ContentCreateRequest(BaseModel):
    entity_type: str = Field(default="certificate")
    slug: str | None = Field(default=None, max_length=255)
    # Attributes for the entity; validated server-side against the entity
    # type's registered JSON Schema.
    data: dict[str, Any]


class ContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: str
    entity_type: str
    slug: str
    status: ContentStatus
    current_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    data: dict[str, Any] | None


class ContentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_id: uuid.UUID
    author_id: uuid.UUID
    created_at: datetime
    data: dict[str, Any]
