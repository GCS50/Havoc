"""Domain-level errors raised by the service layer.

The API layer installs a single handler (see ``app.main``) that turns these
into JSON responses, so services never need to know about HTTP.
"""


class ServiceError(Exception):
    status_code: int = 400
    default_detail: str = "Service error"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class AuthError(ServiceError):
    status_code = 401
    default_detail = "Authentication failed"


class PermissionDeniedError(ServiceError):
    status_code = 403
    default_detail = "Permission denied"


class NotFoundError(ServiceError):
    status_code = 404
    default_detail = "Not found"


class ConflictError(ServiceError):
    status_code = 409
    default_detail = "Conflict"


class SchemaValidationError(ServiceError):
    status_code = 422
    default_detail = "Payload failed schema validation"

    def __init__(self, detail: str | None = None, errors: list[str] | None = None):
        super().__init__(detail)
        self.errors = errors or []
