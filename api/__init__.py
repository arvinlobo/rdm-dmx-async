"""
Optional FastAPI REST API for rdm_dmx_async.

A standalone application that consumes `rdm_dmx_async` as a regular
dependency - kept out of the `rdm_dmx_async` package itself so the library
has no FastAPI/uvicorn dependency and no opinion about how it's exposed.

Requires the `api` extra (`pip install rdm-dmx-async[api]`).
"""

from .app import create_app

__all__ = ["create_app"]
