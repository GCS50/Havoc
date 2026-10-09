"""Pydantic request/response schemas.

Havoc is self-hosted, often on an internal network where addresses like
``admin@havoc.local`` are normal. email-validator (used by ``EmailStr``)
rejects the special-use ``.local`` domain by default; its documented way to
allow it is to remove the name from this module-level list.
"""

import email_validator

if "local" in email_validator.SPECIAL_USE_DOMAIN_NAMES:
    email_validator.SPECIAL_USE_DOMAIN_NAMES.remove("local")
