"""Generic entity storage: ``content`` + immutable ``content_versions``.

``content`` is the stable handle for an entity (a certificate, later other
types). Every change appends a new ``content_versions`` row; existing version
rows are never updated. ``content.current_version_id`` points at the row that
is currently in effect.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ContentStatus


class Content(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content"
    __table_args__ = (
        UniqueConstraint("project_id", "entity_type", "slug", name="uq_content_project_type_slug"),
    )

    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Logical reference to ``entity_types.name``.
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[ContentStatus] = mapped_column(
        SAEnum(ContentStatus, name="content_status", create_type=False),
        default=ContentStatus.draft,
        nullable=False,
    )

    # Nullable until the first version exists. ``use_alter`` breaks the
    # circular FK (content <-> content_versions) at DDL time.
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("content_versions.id", use_alter=True, name="fk_content_current_version"),
        nullable=True,
    )

    versions: Mapped[list["ContentVersion"]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
        order_by="ContentVersion.created_at",
        foreign_keys="ContentVersion.content_id",
    )


class ContentVersion(UUIDMixin, Base):
    __tablename__ = "content_versions"

    content_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("content.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The actual attributes for this entity type (validated against the
    # entity type's JSON Schema before insert).
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    content: Mapped["Content"] = relationship(
        back_populates="versions",
        foreign_keys=[content_id],
    )
