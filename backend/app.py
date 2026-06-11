"""FastAPI application factory for the mova-mc web interface.

In development: Vite dev server (port 5173) proxies /api/* to this server.
In production: this server also serves the pre-built SPA from ``static/``.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routes.catalog import router as catalog_router
from backend.routes.config import router as config_router
from backend.routes.jobs import router as jobs_router
from backend.routes.mods import router as mods_router

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(*, dev: bool = False) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    dev:
        When True, enables permissive CORS so the Vite dev server (port 5173)
        can call the API without CORS errors.  Never set this in production.
    """
    app = FastAPI(
        title="MovaMC Web",
        description="Translate Minecraft mod language files via a browser UI.",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    if dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(catalog_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(mods_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")

    if _STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="spa")

    return app
