#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p app
mkdir -p app/routes

# 1) logging_mw stub
cat > app/logging_mw.py <<'PY'
from __future__ import annotations

from typing import Callable, Awaitable

from starlette.requests import Request
from starlette.responses import Response


async def logging_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """
    Simple logging stub. In production you can add real logging here.
    """
    response = await call_next(request)
    return response
PY

# 2) limit_body stub
cat > app/limit_body.py <<'PY'
from __future__ import annotations

from typing import Callable, Awaitable

from starlette.requests import Request
from starlette.responses import Response


async def limit_body_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """
    Stub body-size limiting middleware. Currently a no-op.
    """
    response = await call_next(request)
    return response
PY

# 3) rate_limit stub
cat > app/rate_limit.py <<'PY'
from __future__ import annotations

from typing import Callable, Awaitable

from starlette.requests import Request
from starlette.responses import Response


async def rate_limit_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """
    Stub rate limiting middleware. Currently a no-op.
    """
    response = await call_next(request)
    return response
PY

# 4) routes package init
cat > app/routes/__init__.py <<'PY'
"""
Stub routes package.

These routers are placeholders so main.py imports succeed.
Replace with real implementations later.
"""
PY

# Helper to write a simple router stub
write_router_stub() {
  local module_path="$1"
  local prefix="$2"
  local tag="$3"

  cat > "$module_path" <<PY
from fastapi import APIRouter

router = APIRouter(prefix="${prefix}", tags=["${tag}"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "${tag} stub"}
PY
}

# 5) individual route stubs
write_router_stub "app/routes/agent.py" "/agent" "agent"
write_router_stub "app/routes/spool.py" "/spool" "spool"
write_router_stub "app/routes/spool_ui.py" "/spool-ui" "spool-ui"
write_router_stub "app/routes/webhook.py" "/webhook" "webhook"
write_router_stub "app/routes/vision_debug.py" "/vision-debug" "vision-debug"
write_router_stub "app/routes/vision_predict.py" "/vision-predict" "vision-predict"
write_router_stub "app/routes/vision_ops.py" "/vision-ops" "vision-ops"
write_router_stub "app/routes/vision_ingest.py" "/vision-ingest" "vision-ingest"
write_router_stub "app/routes/vision_search.py" "/vision-search" "vision-search"
write_router_stub "app/routes/spool_ops.py" "/spool-ops" "spool-ops"
write_router_stub "app/routes/manifests.py" "/manifests" "manifests"
write_router_stub "app/routes/ops.py" "/ops" "ops"
write_router_stub "app/routes/marketplace.py" "/marketplace" "marketplace"

echo "Fixed stub modules for logging_mw, limit_body, rate_limit, and app/routes/*"
