"""Utilidades compartidas para lectura de sysfs y conversión numérica."""

from __future__ import annotations

from pathlib import Path

_GB = 1024**3
_MIB = 1024**2

_NVIDIA_VENDOR = "0x10de"
_INTEL_VENDOR = "0x8086"
_AMD_VENDOR = "0x1002"

_VENDOR_NAMES: dict[str, str] = {
    _INTEL_VENDOR: "Intel Integrated Graphics",
    _AMD_VENDOR: "AMD Radeon Graphics",
}


def bytes_to_gb(value: int | float | None) -> float:
    if value is None:
        return 0.0
    return round(float(value) / _GB, 2)


def read_sysfs_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def read_sysfs_int(path: Path) -> int | None:
    raw = read_sysfs_text(path)
    if raw is None:
        return None
    try:
        return int(raw, 0)
    except ValueError:
        return None


def read_sysfs_float(path: Path) -> float | None:
    raw = read_sysfs_text(path)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def vendor_display_name(vendor_id: str | None) -> str:
    if not vendor_id:
        return "Integrated GPU"
    normalized = vendor_id.lower()
    return _VENDOR_NAMES.get(normalized, "Integrated GPU")


def is_dedicated_vendor(vendor_id: str | None) -> bool:
    if not vendor_id:
        return False
    return vendor_id.lower() == _NVIDIA_VENDOR
