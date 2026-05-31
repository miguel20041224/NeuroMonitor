"""Rate limiting perimetral SEC-008 para GET /metrics/snapshot."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict

from fastapi import HTTPException, Request, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from starlette.requests import Request as StarletteRequest

_WINDOW_SECONDS = 1.0
_MAX_REQUESTS = 2
_MAX_KEYS = 4096

_API_TOKEN_HEADER = APIKeyHeader(name="X-API-Token", auto_error=False)

_RATE_LIMIT_BODY = {
    "success": False,
    "code": "ERR_RATE_LIMITED",
    "error": "Demasiadas peticiones",
}


class _TimestampRing:
    """Ring buffer fijo de hasta 2 timestamps monotónicos por clave."""

    __slots__ = ("_slots",)

    def __init__(self) -> None:
        self._slots: list[float] = []

    def count_in_window(self, now: float, window: float) -> int:
        cutoff = now - window
        return sum(1 for ts in self._slots if ts > cutoff)

    def record(self, now: float) -> None:
        if len(self._slots) < 2:
            self._slots.append(now)
        else:
            self._slots[0] = self._slots[1]
            self._slots[1] = now


class RateLimitStore:
    """Ventana deslizante acotada con evicción LRU manual."""

    def __init__(
        self,
        *,
        max_keys: int = _MAX_KEYS,
        window: float = _WINDOW_SECONDS,
        max_requests: int = _MAX_REQUESTS,
    ) -> None:
        self._max_keys = max_keys
        self._window = window
        self._max_requests = max_requests
        self._entries: OrderedDict[str, _TimestampRing] = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        if now is None:
            now = time.monotonic()

        with self._lock:
            ring = self._entries.get(key)
            if ring is None:
                if len(self._entries) >= self._max_keys:
                    self._entries.popitem(last=False)
                ring = _TimestampRing()
                self._entries[key] = ring
            else:
                self._entries.move_to_end(key)

            if ring.count_in_window(now, self._window) >= self._max_requests:
                return False

            ring.record(now)
            return True


_store = RateLimitStore()


def rate_limit_guard(
    request: Request,
    api_token: str | None = Security(_API_TOKEN_HEADER),
) -> None:
    """Guardia perimetral: 2 req/s por clave IP|token antes de auth (SEC-008)."""
    client_ip = request.client.host if request.client else "unknown"
    token = api_token or ""
    key = f"{client_ip}|{token}"

    if not _store.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_RATE_LIMIT_BODY,
        )


def register_rate_limit_exception_handler(app) -> None:
    """Respuesta 429 opaca sin envoltorio ``detail`` de FastAPI."""

    from fastapi import FastAPI
    from fastapi.exception_handlers import http_exception_handler

    if not isinstance(app, FastAPI):
        return

    @app.exception_handler(HTTPException)
    async def _opaque_rate_limit_handler(
        request: StarletteRequest,
        exc: HTTPException,
    ) -> JSONResponse:
        if (
            exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            and isinstance(exc.detail, dict)
            and exc.detail.get("code") == "ERR_RATE_LIMITED"
        ):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=_RATE_LIMIT_BODY,
            )
        return await http_exception_handler(request, exc)
