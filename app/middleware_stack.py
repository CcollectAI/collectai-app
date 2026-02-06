"""
Middleware stack for the collectors backend.

main.py expects:
    from app.middleware_stack import install_middlewares

Installs CORS and security-related middleware.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Allowed origins for CORS - configure via environment variable
# Default allows localhost/dev origins; production should set explicit list
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8080,http://localhost:8081,http://127.0.0.1:3000,http://127.0.0.1:8080,http://127.0.0.1:8081,exp://localhost:*,exp://192.168.*:*,exp://10.*:*,https://app.collectai.io"
).split(",")

# Trusted hosts - set in production to your actual domains
TRUSTED_HOSTS = os.getenv("TRUSTED_HOSTS", "").split(",") if os.getenv("TRUSTED_HOSTS") else []


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

    return app
