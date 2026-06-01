"""Sondeo de almacenamiento en discos activos vía psutil."""

from __future__ import annotations

import logging

import psutil

from neuromonitor.telemetry.models import DiskSnapshot
from neuromonitor.telemetry.probes._sysfs import bytes_to_gb

logger = logging.getLogger(__name__)


def probe_disks() -> list[DiskSnapshot]:
    disks: list[DiskSnapshot] = []
    try:
        partitions = psutil.disk_partitions(all=False)
    except (OSError, RuntimeError) as exc:
        logger.debug("disk_partitions falló: %s", exc)
        return disks

    for part in partitions:
        if not part.mountpoint or not part.fstype:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError) as exc:
            logger.debug("disk_usage omitido %s: %s", part.mountpoint, exc)
            continue

        disks.append(
            DiskSnapshot(
                mountpoint=part.mountpoint,
                total_gb=bytes_to_gb(usage.total),
                used_gb=bytes_to_gb(usage.used),
                percent=round(float(usage.percent), 2),
            )
        )

    return disks
