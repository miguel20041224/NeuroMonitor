import threading
import time
from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from neuromonitor.api.deps import get_monitor_service
from neuromonitor.api.rate_limit import rate_limit_guard
from neuromonitor.config import get_settings
from neuromonitor.models.snapshot import SystemSnapshot
from neuromonitor.services.monitor_service import MonitorService

router = APIRouter()

_API_TOKEN_HEADER = APIKeyHeader(name="X-API-Token", auto_error=False)

_SNAPSHOT_CACHE_TTL_SECONDS = 0.5

_cache_lock = threading.Lock()
_cached_snapshot: SystemSnapshot | None = None
_cache_captured_at: float = 0.0


def require_api_token(
    api_token: str | None = Security(_API_TOKEN_HEADER),
) -> None:
    """Exige cabecera X-API-Token válida para lectura de métricas (SEC-001)."""
    expected = get_settings().api_token
    if (
        expected is None
        or api_token is None
        or not compare_digest(api_token, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de API inválido o ausente",
        )


def _snapshot_cache_get(monitor: MonitorService) -> SystemSnapshot:
    """Cache TTL 500 ms con lock para evitar thundering herd (REC-029 / LAB_09)."""
    global _cached_snapshot, _cache_captured_at

    now = time.monotonic()
    cached = _cached_snapshot
    if cached is not None and (now - _cache_captured_at) < _SNAPSHOT_CACHE_TTL_SECONDS:
        return cached

    with _cache_lock:
        now = time.monotonic()
        cached = _cached_snapshot
        if cached is not None and (now - _cache_captured_at) < _SNAPSHOT_CACHE_TTL_SECONDS:
            return cached

        snapshot = monitor.capture_snapshot()
        _cached_snapshot = snapshot
        _cache_captured_at = time.monotonic()
        return snapshot


@router.get("/snapshot", response_model=SystemSnapshot)
def get_snapshot(
    _: None = Depends(rate_limit_guard),
    __: None = Depends(require_api_token),
    monitor: MonitorService = Depends(get_monitor_service),
) -> SystemSnapshot:
    """Lectura puntual para polling HTTP del frontend."""
    return _snapshot_cache_get(monitor)
