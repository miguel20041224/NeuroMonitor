import logging

import psutil
from pydantic import ValidationError

from neuromonitor.collectors.base import MetricCollector
from neuromonitor.collectors.sanitize import clamp_percent
from neuromonitor.models.metrics import MemoryMetrics

logger = logging.getLogger(__name__)

ERR_MEMORY_DEGRADED = "ERR_MEMORY_DEGRADED"


class MemoryCollector(MetricCollector):
    @staticmethod
    def _degraded_fallback() -> MemoryMetrics:
        return MemoryMetrics(
            total_bytes=0,
            used_bytes=0,
            available_bytes=0,
            percent=0.0,
            swap_total_bytes=0,
            swap_used_bytes=0,
            swap_percent=0.0,
            message=ERR_MEMORY_DEGRADED,
        )

    def _collect_metrics(self) -> MemoryMetrics:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return MemoryMetrics(
            total_bytes=vm.total,
            used_bytes=vm.used,
            available_bytes=vm.available,
            percent=clamp_percent(float(vm.percent)),
            swap_total_bytes=swap.total,
            swap_used_bytes=swap.used,
            swap_percent=clamp_percent(float(swap.percent)),
        )

    def collect(self) -> MemoryMetrics:
        try:
            return self._collect_metrics()
        except (ValidationError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Memory collector degradado: %s", exc, exc_info=True)
            return self._degraded_fallback()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Memory collector degradado (inesperado): %s", exc)
            return self._degraded_fallback()
