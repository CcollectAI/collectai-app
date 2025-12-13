from __future__ import annotations

import os
import pathlib

try:
    from dotenv import load_dotenv  # provided by python-dotenv
except Exception:
    load_dotenv = None


def ensure_env():
    # If already set, nothing to do
    if "DATABASE_URL" in os.environ:
        return
    # Try to load a .env from project root
    if load_dotenv:
        env = pathlib.Path.cwd() / ".env"
        if env.exists():
            load_dotenv(env)
