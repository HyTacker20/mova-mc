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
from backend.routes.logs import attach_log_sink, detach_log_sink
from backend.routes.logs import router as logs_router
from backend.routes.mods import router as mods_router

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(*, dev: bool = False) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    dev:
        When True, enables permissive CORS so the Vite dev server (port 5173)
        can call the API without CORS errors.  In *dev* mode the server does
        **not** serve static files — Vite handles the frontend via HMR.

        When called as a uvicorn factory (``uvicorn.run(…, factory=True)``)
        this parameter is ``False``; the factory reads the ``MOVAMC_DEV``
        environment variable instead.
    """
    import os

    if not dev and os.environ.get("MOVAMC_DEV") == "1":
        dev = True
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
    app.include_router(logs_router, prefix="/api")

    @app.on_event("startup")
    async def _startup() -> None:
        attach_log_sink()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        detach_log_sink()

    # In dev mode Vite serves the frontend (with HMR); only mount static
    # files in production mode.
    if not dev and _STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="spa")

    return app
