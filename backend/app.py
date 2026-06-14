"""FastAPI application factory for the mova-mc web interface.

In development: Vite dev server (port 5173) proxies /api/* to this server.
In production: this server also serves the pre-built SPA from ``static/``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
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


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup: configure logging, attach loguru→SSE sink, log config."""
    from loguru import logger

    from app.core.config_loader import find_config_file, load_config
    from app.logging_config import is_logging_configured, setup_logging

    if not is_logging_configured():
        setup_logging(console_level="INFO")
    attach_log_sink()

    # ── Log current config for debugging context ──
    try:
        # Try CWD first, then fall back to ".".
        config_path = find_config_file(".")
        if config_path:
            raw = load_config(config_path)
            logger.info(
                "Config loaded from {} | provider={} model={} source={} target={} "
                "output={} output_mode={} cache={} qa={} workers={}",
                config_path.name,
                raw.get("provider", "?"),
                raw.get("model", "?"),
                raw.get("source", "?"),
                raw.get("target", "?"),
                raw.get("output", "?"),
                raw.get("output_mode", "?"),
                "off" if raw.get("no_cache") else "on",
                "on" if raw.get("qa", {}).get("judge") else "off",
                raw.get("workers", "?"),
            )
        else:
            logger.info("No config file found — using defaults")
    except Exception:
        logger.debug("Could not log config at startup")

    yield
    detach_log_sink()


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
        lifespan=_lifespan,
    )

    if dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(catalog_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(mods_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    app.include_router(logs_router, prefix="/api")

    # In dev mode Vite serves the frontend (with HMR); only mount static
    # files in production mode.
    if not dev and _STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="spa")

    return app
