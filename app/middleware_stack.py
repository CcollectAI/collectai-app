"""
Middleware stack for the collectors backend.

main.py expects:
    from app.middleware_stack import install_middlewares

Installs CORS and security-related middleware.
"""

from typing import Callable, Awaitable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import CORS_ORIGINS, TRUSTED_HOSTS


def install_middlewares(app: FastAPI) -> FastAPI:
    """
    Install core middleware stack:
    - CORS for cross-origin requests (mobile app, web frontend)
    - TrustedHost for production security (if configured)
    """
    # CORS middleware - allow mobile app and web frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trusted host middleware (only if explicitly configured)
    if TRUSTED_HOSTS and TRUSTED_HOSTS != [""]:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=TRUSTED_HOSTS,
        )

    # Security headers middleware
    @app.middleware("http")
    async def security_headers_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    return app
