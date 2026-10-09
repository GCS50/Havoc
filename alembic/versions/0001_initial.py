"""initial schema + certificate entity_type seed

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-01

"""

import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.seeds.certificate_schema import CERTIFICATE_ENTITY_TYPE, CERTIFICATE_JSON_SCHEMA

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# create_type=False: we create/drop the PG enum types explicitly below so
# that create_table does not try to (re)create them.
user_status = postgresql.ENUM(
    "pending", "active", "suspended", name="user_status", create_type=False
)
user_role = postgresql.ENUM(
    "employee", "intern", "admin", name="user_role", create_type=False
)
content_status = postgresql.ENUM(
    "draft", "published", "revoked", name="content_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    user_status.create(bind, checkfirst=True)
    user_role.create(bind, checkfirst=True)
    content_status.create(bind, checkfirst=True)

    now = sa.text("now()")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", user_status, nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("project_id", sa.String(64), server_default="moon", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_project_id", "users", ["project_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index("ix_api_keys_project_id", "api_keys", ["project_id"])

    op.create_table(
        "entity_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("json_schema", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    )
    op.create_index("ix_entity_types_name", "entity_types", ["name"], unique=True)

    op.create_table(
        "content",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("status", content_status, nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.UniqueConstraint(
            "project_id", "entity_type", "slug", name="uq_content_project_type_slug"
        ),
    )
    op.create_index("ix_content_project_id", "content", ["project_id"])
    op.create_index("ix_content_entity_type", "content", ["entity_type"])

    op.create_table(
        "content_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data", postgresql.JSONB, nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.ForeignKeyConstraint(["content_id"], ["content.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
    )
    op.create_index("ix_content_versions_content_id", "content_versions", ["content_id"])

    op.create_foreign_key(
        "fk_content_current_version",
        "content",
        "content_versions",
        ["current_version_id"],
        ["id"],
    )

    # ---- Seed: built-in "certificate" entity type ----
    # Rendered as a plain statement (works both online and with `--sql`);
    # the values are fully controlled constants, not user input.
    schema_literal = json.dumps(CERTIFICATE_JSON_SCHEMA).replace("'", "''")
    op.execute(
        sa.text(
            "INSERT INTO entity_types (id, name, json_schema, created_at) VALUES ("
            f"'{uuid.uuid4()}', '{CERTIFICATE_ENTITY_TYPE}', '{schema_literal}'::jsonb, now())"
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_content_current_version", "content", type_="foreignkey")
    op.drop_table("content_versions")
    op.drop_table("content")
    op.drop_table("entity_types")
    op.drop_table("api_keys")
    op.drop_table("users")
    bind = op.get_bind()
    content_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
    user_status.drop(bind, checkfirst=True)
