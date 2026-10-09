"""Havoc API application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.seeds.runtime import ensure_seed_entity_types
from app.services.errors import SchemaValidationError, ServiceError

WEB_DIR = Path(__file__).parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keep the entity-type registry in sync with the built-in schemas.
    await ensure_seed_entity_types()
    yield


app = FastAPI(
    title="Havoc API",
    version="0.1.0",
    description="API-first platform for storing, versioning and serving structured data.",
    lifespan=lifespan,
)


@app.exception_handler(ServiceError)
async def _service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    body: dict[str, object] = {"detail": exc.detail}
    if isinstance(exc, SchemaValidationError) and exc.errors:
        body["errors"] = exc.errors
    return JSONResponse(status_code=exc.status_code, content=body)


app.include_router(api_router, prefix="/v1")


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Web UI: a static single-page app that uses the /v1 API like any other client.
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
async def web_ui() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
