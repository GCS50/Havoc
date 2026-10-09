"""Schema registry: one row per entity type (e.g. "certificate")."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class EntityType(UUIDMixin, Base):
    __tablename__ = "entity_types"

    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # JSON Schema used to validate ``content_versions.data`` for this type.
    json_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
