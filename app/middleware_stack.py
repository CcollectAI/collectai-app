"""
Stub middleware stack for the collectors backend.

main.py expects:
    from app.middleware_stack import install_middlewares

This stub simply returns the app unchanged. You can replace it later
with real CORSMiddleware, logging, auth, etc.
"""

from fastapi import FastAPI


def install_middlewares(app: FastAPI) -> FastAPI:
    # TODO: add real middleware (CORS, logging, security, etc.)
    return app
