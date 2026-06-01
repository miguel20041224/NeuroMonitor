"""Sondeo de memoria RAM vía psutil."""

from __future__ import annotations

import logging

import psutil

from neuromonitor.telemetry.models import RamSnapshot
from neuromonitor.telemetry.probes._sysfs import bytes_to_gb

logger = logging.getLogger(__name__)


def probe_ram() -> RamSnapshot:
    try:
        vm = psutil.virtual_memory()
        return RamSnapshot(
            total_gb=bytes_to_gb(vm.total),
            available_gb=bytes_to_gb(vm.available),
            used_gb=bytes_to_gb(vm.used),
            percent=round(float(vm.percent), 2),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("RAM probe falló: %s", exc)
        return RamSnapshot()
