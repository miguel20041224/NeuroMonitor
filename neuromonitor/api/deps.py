from neuromonitor.config import get_settings
from neuromonitor.services.monitor_service import MonitorService


def get_monitor_service() -> MonitorService:
    """Factory sin @lru_cache para reflejar settings en caliente (REC-030)."""
    return MonitorService(settings=get_settings())


def _clear_monitor_service_cache() -> None:
    """Compatibilidad con labs que invocan cache_clear tras quitar @lru_cache."""


get_monitor_service.cache_clear = _clear_monitor_service_cache  # type: ignore[attr-defined]
