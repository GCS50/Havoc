"""Aggregates all v1 routers."""

from fastapi import APIRouter

from app.api.v1 import admin, auth, content

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(content.router)
