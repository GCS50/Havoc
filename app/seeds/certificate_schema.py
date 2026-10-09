"""Single source of truth for the built-in "certificate" entity type.

Used both by the initial Alembic migration (to seed the row) and by the
runtime startup check that keeps the registry row in sync.
"""

from typing import Any

CERTIFICATE_ENTITY_TYPE = "certificate"

# JSON Schema (2020-12) for ``content_versions.data`` of a certificate.
# ``verification_token`` is generated server-side on creation.
CERTIFICATE_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "certificate",
    "type": "object",
    "additionalProperties": False,
    "required": ["type", "title", "issued_to", "issued_by", "issue_date", "verification_token"],
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "certificate",
                "course_certificate",
                "award",
                "reference",
                "general_training",
            ],
        },
        "title": {"type": "string", "minLength": 1},
        "issued_to": {"type": "string", "format": "uuid"},
        "issued_by": {"type": "string", "format": "uuid"},
        "issue_date": {"type": "string", "format": "date"},
        "valid_from": {"type": "string", "format": "date"},
        "valid_until": {"type": "string", "format": "date"},
        "course_link": {"type": "string", "format": "uri"},
        "pdf_url": {"type": "string"},
        "verification_token": {"type": "string", "minLength": 1},
    },
}
