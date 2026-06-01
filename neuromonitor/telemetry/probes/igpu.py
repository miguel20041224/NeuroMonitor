"""Sondeo de GPU integrada vía sysfs (/sys/class/drm)."""

from __future__ import annotations

import logging
from pathlib import Path

from neuromonitor.telemetry.models import IntegratedGpuSnapshot
from neuromonitor.telemetry.probes._sysfs import (
    is_dedicated_vendor,
    read_sysfs_float,
    read_sysfs_int,
    read_sysfs_text,
    vendor_display_name,
)

logger = logging.getLogger(__name__)

_DRM_BASE = Path("/sys/class/drm")
_BUSY_NODES = ("gpu_busy_percent", "gt_busy_percent", "busy_percent")


def _drm_card_dirs() -> list[Path]:
    cards: list[Path] = []
    try:
        if not _DRM_BASE.is_dir():
            return cards
        for entry in sorted(_DRM_BASE.iterdir()):
            if entry.name.startswith("card") and entry.is_dir():
                cards.append(entry)
    except OSError as exc:
        logger.debug("Listado DRM falló: %s", exc)
    return cards


def _read_utilization(device_dir: Path) -> float | None:
    for node in _BUSY_NODES:
        value = read_sysfs_float(device_dir / node)
        if value is not None:
            return round(value, 2)
    return None


def _read_gpu_name(device_dir: Path, vendor_id: str | None) -> str:
    for candidate in (
        device_dir / "product_name",
        device_dir / "name",
        device_dir / "uevent",
    ):
        raw = read_sysfs_text(candidate)
        if not raw:
            continue
        if candidate.name == "uevent":
            for line in raw.splitlines():
                if line.startswith("DRIVER=") and len(line) > 7:
                    driver = line.split("=", 1)[1]
                    if driver and driver != "(null)":
                        return vendor_display_name(vendor_id).replace(
                            "Integrated Graphics", f"{driver.title()} Graphics"
                        )
        else:
            return raw
    return vendor_display_name(vendor_id)


def _probe_from_card(card_dir: Path) -> IntegratedGpuSnapshot | None:
    vendor_raw = read_sysfs_text(card_dir / "device" / "vendor")
    if is_dedicated_vendor(vendor_raw):
        return None

    device_dir = card_dir / "device"
    if not device_dir.is_dir():
        return None

    utilization = _read_utilization(device_dir)
    mem_used = read_sysfs_int(device_dir / "mem_info_vram_usage")
    mem_total = read_sysfs_int(device_dir / "mem_info_vram_total")
    mem_pct: float | None = None
    if mem_used is not None and mem_total and mem_total > 0:
        mem_pct = round(mem_used / mem_total * 100.0, 2)

    return IntegratedGpuSnapshot(
        available=True,
        name=_read_gpu_name(device_dir, vendor_raw),
        utilization_percent=utilization if utilization is not None else 0.0,
        source="sysfs",
        memory_used_bytes=mem_used,
        memory_total_bytes=mem_total,
        memory_percent=mem_pct,
        error=None,
    )


def _fallback_card0() -> IntegratedGpuSnapshot:
    """Fallback limpio sobre card0 cuando el barrido general no responde."""
    card0 = _DRM_BASE / "card0" / "device"
    if not card0.is_dir():
        return IntegratedGpuSnapshot(
            available=False,
            name=None,
            utilization_percent=None,
            error="igpu_sysfs_unavailable",
        )

    vendor_raw = read_sysfs_text(card0 / "vendor")
    utilization = _read_utilization(card0)
    return IntegratedGpuSnapshot(
        available=utilization is not None or vendor_raw is not None,
        name=_read_gpu_name(card0, vendor_raw) if vendor_raw else None,
        utilization_percent=utilization if utilization is not None else 0.0,
        source="sysfs_fallback",
        error=None if utilization is not None else "igpu_busy_node_blocked",
    )


def probe_integrated_gpu() -> IntegratedGpuSnapshot:
    try:
        for card_dir in _drm_card_dirs():
            snapshot = _probe_from_card(card_dir)
            if snapshot is not None:
                return snapshot
    except OSError as exc:
        logger.debug("iGPU sysfs falló: %s", exc)

    try:
        return _fallback_card0()
    except Exception as exc:  # noqa: BLE001
        logger.debug("iGPU fallback falló: %s", exc)
        return IntegratedGpuSnapshot(
            available=False,
            name=None,
            utilization_percent=None,
            error=str(exc),
        )
