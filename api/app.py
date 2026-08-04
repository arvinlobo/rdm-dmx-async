"""
FastAPI application factory for the rdm-dmx-async REST API.

Run with:
    uvicorn api.app:app --reload

The NetworkManager is NOT started automatically - call POST /network/connect
first (hardware access is explicit, never implicit on process startup).

If `frontend/dist` exists (i.e. `npm run build` has been run), it is served
at "/" from this same process, so a single `uvicorn api.app:app` command runs
both the API and the UI on one origin/port - no separate Vite server needed.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from rdm_dmx_async.application.network_manager import NetworkManager

from .logging_config import configure_logging
from .routers import capabilities, devices, dmx, network

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

_log_file = configure_logging()
logging.getLogger(__name__).info("Logging to %s", _log_file)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.network_manager: NetworkManager | None = None
    try:
        yield
    finally:
        manager = app.state.network_manager
        if manager is not None and manager.is_active:
            await manager.stop()


def create_app() -> FastAPI:
    """Build the FastAPI application (call once per process)."""
    app = FastAPI(
        title="rdm-dmx-async API",
        description="REST API for RDM device discovery/control and DMX output.",
        version="1.0.0-alpha",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        # Vite auto-increments its port (5173, 5174, ...) if the default is
        # already in use, so match any localhost dev-server port rather than
        # hardcoding one.
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(network.router)
    app.include_router(devices.router)
    app.include_router(dmx.router)
    app.include_router(capabilities.router)

    if _FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")

    return app


app = create_app()
