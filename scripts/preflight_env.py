#!/usr/bin/env python3
"""
Pre-flight: validate environment before service starts.

Thin wrapper around `app.config.validate_config()` so env validation runs
as an ExecStartPre gate (before uvicorn imports anything). Missing
REQUIRED vars exit 1 loudly with a systemd-visible error message, instead
of getting lost somewhere inside the FastAPI lifespan hook.

Usage:
  python3 scripts/preflight_env.py
"""
from __future__ import annotations

import logging
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "server"))


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [preflight_env] %(levelname)s: %(message)s",
    )
    logger = logging.getLogger("preflight_env")

    try:
        from app.config import validate_config
    except Exception as e:
        logger.critical("Failed to import app.config: %s", e)
        return 1

    try:
        validate_config()
    except SystemExit as e:
        logger.critical("Env validation failed (SystemExit=%s)", e.code)
        return int(e.code) if isinstance(e.code, int) else 1
    except Exception as e:
        logger.critical("Env validation raised unexpected error: %s", e)
        return 1

    logger.info("Env validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
