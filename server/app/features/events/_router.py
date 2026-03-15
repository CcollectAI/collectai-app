"""Shared router instance for the events sub-package.

All sub-modules import ``router`` from here to register their endpoints.
This avoids circular imports between __init__.py and the sub-modules.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/events", tags=["Events"])
