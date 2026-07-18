"""API-key authentication middleware.

When ``auth.api_key`` is configured, requests to protected paths must send it
via the ``X-API-Key`` header (or ``Authorization: Bearer <key>``). Health,
discovery and console assets stay public.
"""

from __future__ import annotations

import hmac
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {"/", "/health", "/.well-known/agent.json"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str) -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        provided = request.headers.get("x-api-key")
        if provided is None:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                provided = auth[7:]

        if provided is None or not hmac.compare_digest(provided, self._api_key):
            logger.warning("Rejected unauthenticated request to %s", request.url.path)
            return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)
        return await call_next(request)
