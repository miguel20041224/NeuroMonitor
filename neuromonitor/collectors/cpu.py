import logging
import os

import psutil
from pydantic import ValidationError

from neuromonitor.collectors.base import MetricCollector
from neuromonitor.collectors.sanitize import clamp_percent
from neuromonitor.models.metrics import CpuCoreMetrics, CpuMetrics

logger = logging.getLogger(__name__)

ERR_CPU_DEGRADED = "ERR_CPU_DEGRADED"


class CpuCollector(MetricCollector):
    def __init__(self, sample_interval: float = 0.1) -> None:
        self._interval = sample_interval

    @staticmethod
    def _degraded_fallback() -> CpuMetrics:
        try:
            logical = psutil.cpu_count(logical=True) or 0
            physical = psutil.cpu_count(logical=False)
        except Exception:  # noqa: BLE001
            logical = 0
            physical = None
        return CpuMetrics(
            percent=0.0,
            per_core=[],
            frequency_mhz=None,
            load_avg_1m=None,
            logical_cores=logical,
            physical_cores=physical,
            message=ERR_CPU_DEGRADED,
        )

    def _collect_metrics(self) -> CpuMetrics:
        per_core_raw = psutil.cpu_percent(
            interval=self._interval, percpu=True
        )
        core_count = len(per_core_raw) or 1
        global_percent = clamp_percent(sum(per_core_raw) / core_count)
        per_core = [
            CpuCoreMetrics(core_id=i, percent=clamp_percent(float(p)))
            for i, p in enumerate(per_core_raw)
        ]

        freq = psutil.cpu_freq()
        load_avg: float | None = None
        if hasattr(os, "getloadavg"):
            load_avg = float(os.getloadavg()[0])

        return CpuMetrics(
            percent=global_percent,
            per_core=per_core,
            frequency_mhz=freq.current if freq else None,
            load_avg_1m=load_avg,
            logical_cores=psutil.cpu_count(logical=True) or 0,
            physical_cores=psutil.cpu_count(logical=False),
        )

    def collect(self) -> CpuMetrics:
        try:
            return self._collect_metrics()
        except (ValidationError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("CPU collector degradado: %s", exc, exc_info=True)
            return self._degraded_fallback()
        except Exception as exc:  # noqa: BLE001
            logger.exception("CPU collector degradado (inesperado): %s", exc)
            return self._degraded_fallback()
