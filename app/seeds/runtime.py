"""Startup seeding: keep the entity-type registry in sync with built-ins.

The initial migration already inserts the "certificate" row; this makes the
schema self-healing if the JSON Schema changes in a later code release
without a dedicated data migration.
"""

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.entity_type import EntityType
from app.seeds.certificate_schema import CERTIFICATE_ENTITY_TYPE, CERTIFICATE_JSON_SCHEMA

_BUILTIN_ENTITY_TYPES = {
    CERTIFICATE_ENTITY_TYPE: CERTIFICATE_JSON_SCHEMA,
}


async def ensure_seed_entity_types() -> None:
    async with AsyncSessionLocal() as db:
        for name, schema in _BUILTIN_ENTITY_TYPES.items():
            row = await db.scalar(select(EntityType).where(EntityType.name == name))
            if row is None:
                db.add(EntityType(name=name, json_schema=schema))
            elif row.json_schema != schema:
                row.json_schema = schema
        await db.commit()
