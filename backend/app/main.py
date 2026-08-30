"""FastAPI application entry point (compatibility re-export).

The application instance and route registration live in :mod:`app.app`;
``uvicorn app.main:app`` keeps working through the re-export below.
"""
from .app import app

__all__ = ["app"]
