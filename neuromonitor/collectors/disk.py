import logging
import time

import psutil
from pydantic import ValidationError

from neuromonitor.collectors.base import MetricCollector
from neuromonitor.collectors.sanitize import clamp_percent
from neuromonitor.models.metrics import DiskMetrics, DiskPartitionMetrics

logger = logging.getLogger(__name__)

ERR_DISK_DEGRADED = "ERR_DISK_DEGRADED"


class DiskCollector(MetricCollector):
    def __init__(self) -> None:
        self._last_io = None
        self._last_io_time: float | None = None

    @staticmethod
    def _degraded_fallback() -> DiskMetrics:
        return DiskMetrics(
            partitions=[],
            read_bytes_per_sec=None,
            write_bytes_per_sec=None,
            message=ERR_DISK_DEGRADED,
        )

    def _collect_partitions(self) -> list[DiskPartitionMetrics]:
        partitions: list[DiskPartitionMetrics] = []
        for part in psutil.disk_partitions(all=False):
            if part.fstype and part.mountpoint:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                except (PermissionError, OSError):
                    continue
                partitions.append(
                    DiskPartitionMetrics(
                        device=part.device,
                        mountpoint=part.mountpoint,
                        fstype=part.fstype,
                        total_bytes=usage.total,
                        used_bytes=usage.used,
                        free_bytes=usage.free,
                        percent=clamp_percent(float(usage.percent)),
                    )
                )
        return partitions

    def _collect_io_rates(self) -> tuple[float | None, float | None]:
        read_bps: float | None = None
        write_bps: float | None = None
        io = psutil.disk_io_counters()
        now = time.time()
        if io and self._last_io and self._last_io_time:
            dt = now - self._last_io_time
            if dt > 0:
                read_delta = io.read_bytes - self._last_io.read_bytes
                write_delta = io.write_bytes - self._last_io.write_bytes
                if read_delta < 0 or write_delta < 0:
                    self._last_io = io
                    self._last_io_time = now
                    return None, None
                read_bps = max(0.0, read_delta / dt)
                write_bps = max(0.0, write_delta / dt)
        if io:
            self._last_io = io
            self._last_io_time = now
        return read_bps, write_bps

    def _collect_metrics(self) -> DiskMetrics:
        read_bps, write_bps = None, None
        try:
            read_bps, write_bps = self._collect_io_rates()
        except (AttributeError, OSError):
            pass

        return DiskMetrics(
            partitions=self._collect_partitions(),
            read_bytes_per_sec=read_bps,
            write_bytes_per_sec=write_bps,
        )

    def collect(self) -> DiskMetrics:
        try:
            return self._collect_metrics()
        except (ValidationError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Disk collector degradado: %s", exc, exc_info=True)
            return self._degraded_fallback()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Disk collector degradado (inesperado): %s", exc)
            return self._degraded_fallback()
