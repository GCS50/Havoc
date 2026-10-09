"""Validate a ``data`` payload against a registered entity-type JSON Schema."""

from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity_type import EntityType
from app.services.errors import NotFoundError, SchemaValidationError

_format_checker = FormatChecker()


async def validate_entity_data(
    db: AsyncSession, *, entity_type: str, data: dict[str, Any]
) -> None:
    schema_row = await db.scalar(
        select(EntityType).where(EntityType.name == entity_type)
    )
    if schema_row is None:
        raise NotFoundError(f"Unknown entity_type '{entity_type}'")

    validator = Draft202012Validator(
        schema_row.json_schema, format_checker=_format_checker
    )
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        messages = [
            f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}" for e in errors
        ]
        raise SchemaValidationError("data failed schema validation", errors=messages)
