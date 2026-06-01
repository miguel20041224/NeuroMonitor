"""Sondeo de GPU dedicada: PCI multi-driver, nvidia-smi y sysfs AMD."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import re
import shutil
from pathlib import Path

from neuromonitor.telemetry.models import DedicatedGpuDeviceSnapshot, DedicatedGpuSnapshot
from neuromonitor.telemetry.probes._dgpu_discovery import DgpuIdentity, discover_dgpu_identity
from neuromonitor.telemetry.probes._gpu_name import sanitize_dgpu_commercial_name
from neuromonitor.telemetry.probes._sysfs import (
    _AMD_VENDOR,
    read_sysfs_float,
    read_sysfs_int,
    read_sysfs_text,
)

logger = logging.getLogger(__name__)

_DRM_BASE = Path("/sys/class/drm")
_NVIDIA_SMI_TIMEOUT_S = 8.0
_NVIDIA_QUERY = (
    "index,name,utilization.gpu,memory.total,memory.used,temperature.gpu"
)
_BUSY_NODES = ("gpu_busy_percent", "gt_busy_percent", "busy_percent")
_CARD_RE = re.compile(r"^card(\d+)$")
_VRAM_USED_NODES = ("mem_info_vram_used", "mem_info_vram_usage")
_VRAM_TOTAL_NODE = "mem_info_vram_total"


def _nvidia_smi_available() -> bool:
    return shutil.which("nvidia-smi") is not None


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text or text.upper() in {"N/A", "[N/A]"}:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _safe_int(value: str | None) -> int | None:
    parsed = _safe_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _bytes_to_mb_int(value: int | None) -> int:
    if value is None or value < 0:
        return 0
    return int(value // (1024 * 1024))


def _make_device(
    *,
    name: str,
    index: int = 0,
    utilization_percent: float = 0.0,
    memory_used_mb: int = 0,
    memory_total_mb: int = 0,
    temperature_c: float | None = None,
) -> DedicatedGpuDeviceSnapshot:
    clean_name = sanitize_dgpu_commercial_name(name)
    mem_pct: float | None = None
    if memory_total_mb > 0:
        mem_pct = round(memory_used_mb / memory_total_mb * 100.0, 2)
    return DedicatedGpuDeviceSnapshot(
        index=index,
        name=clean_name,
        utilization_percent=utilization_percent,
        memory_used_mb=float(memory_used_mb),
        memory_total_mb=float(memory_total_mb),
        memory_used_mib=float(memory_used_mb),
        memory_total_mib=float(memory_total_mb),
        temperature_c=temperature_c,
        memory_percent=mem_pct,
    )


def _is_amdgpu_device_dir(device_dir: Path) -> bool:
    if not device_dir.is_dir():
        return False
    vendor = (read_sysfs_text(device_dir / "vendor") or "").lower()
    if vendor != _AMD_VENDOR:
        return False
    driver_link = device_dir / "driver"
    try:
        if driver_link.is_symlink():
            return "amdgpu" in driver_link.resolve().name
    except OSError:
        pass
    return (device_dir / _VRAM_TOTAL_NODE).is_file()


def _read_amdgpu_vram_bytes(device_dir: Path) -> tuple[int, int]:
    mem_total_b = read_sysfs_int(device_dir / _VRAM_TOTAL_NODE) or 0
    mem_used_b = 0
    for node in _VRAM_USED_NODES:
        value = read_sysfs_int(device_dir / node)
        if value is not None:
            mem_used_b = value
            break
    return mem_used_b, mem_total_b


def _resolve_amdgpu_device_dir(identity: DgpuIdentity) -> tuple[Path, int] | None:
    candidates: list[tuple[Path, int, int]] = []

    if identity.drm_card:
        device_dir = _DRM_BASE / identity.drm_card / "device"
        if _is_amdgpu_device_dir(device_dir):
            used_b, total_b = _read_amdgpu_vram_bytes(device_dir)
            try:
                card_index = int(identity.drm_card.removeprefix("card"))
            except ValueError:
                card_index = 0
            candidates.append((device_dir, card_index, total_b))

    if not _DRM_BASE.is_dir():
        return candidates[0][:2] if candidates else None

    for entry in sorted(_DRM_BASE.iterdir(), key=lambda p: p.name):
        card_match = _CARD_RE.match(entry.name)
        if not card_match:
            continue
        device_dir = entry / "device"
        if not _is_amdgpu_device_dir(device_dir):
            continue
        used_b, total_b = _read_amdgpu_vram_bytes(device_dir)
        card_index = int(card_match.group(1))
        candidates.append((device_dir, card_index, total_b))

    if not candidates:
        return None

    if identity.pci_address:
        for device_dir, card_index, _ in candidates:
            resolved = None
            try:
                resolved = str(device_dir.resolve()).lower()
            except OSError:
                continue
            if identity.pci_address.lower() in resolved:
                return device_dir, card_index

    candidates.sort(key=lambda item: (item[2], item[1]), reverse=True)
    device_dir, card_index, _ = candidates[0]
    return device_dir, card_index


def _detected_only_snapshot(identity: DgpuIdentity) -> DedicatedGpuSnapshot:
    resolved = _resolve_amdgpu_device_dir(identity)
    memory_used_mb = 0
    memory_total_mb = 0
    card_index = 0
    if resolved is not None:
        device_dir, card_index = resolved
        used_b, total_b = _read_amdgpu_vram_bytes(device_dir)
        memory_used_mb = _bytes_to_mb_int(used_b)
        memory_total_mb = _bytes_to_mb_int(total_b)

    return DedicatedGpuSnapshot(
        available=True,
        devices=[
            _make_device(
                name=identity.name,
                index=card_index,
                utilization_percent=0.0,
                memory_used_mb=memory_used_mb,
                memory_total_mb=memory_total_mb,
                temperature_c=None,
            )
        ],
        error=None,
    )


def _parse_nvidia_csv(stdout: str) -> list[DedicatedGpuDeviceSnapshot]:
    devices: list[DedicatedGpuDeviceSnapshot] = []
    reader = csv.reader(io.StringIO(stdout.strip()))
    for row in reader:
        if not row or len(row) < 6:
            continue
        index = _safe_int(row[0])
        if index is None:
            continue
        mem_total = _safe_int(row[3]) or 0
        mem_used = _safe_int(row[4]) or 0
        devices.append(
            _make_device(
                name=row[1].strip(),
                index=index,
                utilization_percent=_safe_float(row[2]) or 0.0,
                memory_used_mb=mem_used,
                memory_total_mb=mem_total,
                temperature_c=_safe_float(row[5]),
            )
        )
    return devices


async def _run_nvidia_smi_async() -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "nvidia-smi",
        f"--query-gpu={_NVIDIA_QUERY}",
        "--format=csv,noheader,nounits",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(),
            timeout=_NVIDIA_SMI_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise TimeoutError("nvidia-smi timeout") from None

    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")
    return proc.returncode or 0, stdout, stderr


def _collect_nvidia_telemetry() -> DedicatedGpuSnapshot | None:
    if not _nvidia_smi_available():
        return None

    try:
        returncode, stdout, stderr = asyncio.run(_run_nvidia_smi_async())
    except (TimeoutError, OSError) as exc:
        logger.debug("nvidia-smi: %s", exc)
        return None

    if returncode != 0:
        logger.debug("nvidia-smi exit %s: %s", returncode, stderr.strip())
        return None

    try:
        devices = _parse_nvidia_csv(stdout)
    except (csv.Error, ValueError) as exc:
        logger.debug("nvidia-smi CSV: %s", exc)
        return None

    if not devices:
        return None

    return DedicatedGpuSnapshot(available=True, devices=devices, error=None)


def _read_utilization(device_dir: Path) -> float | None:
    for node in _BUSY_NODES:
        value = read_sysfs_float(device_dir / node)
        if value is not None:
            return round(value, 2)
    return None


def _read_hwmon_temperature(device_dir: Path) -> float | None:
    hwmon_dir = device_dir / "hwmon"
    if not hwmon_dir.is_dir():
        return None
    try:
        entries = sorted(hwmon_dir.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.startswith("hwmon"):
            continue
        for temp_name in ("temp1_input", "temp2_input"):
            raw = read_sysfs_int(entry / temp_name)
            if raw is not None:
                return round(raw / 1000.0, 1)
    return None


def _estimate_utilization(drm_card: str | None, device_dir: Path) -> float:
    util = _read_utilization(device_dir)
    if util is not None:
        return util

    if drm_card:
        try:
            card_num = int(drm_card.removeprefix("card"))
        except ValueError:
            card_num = None
        if card_num is not None:
            render_dir = _DRM_BASE / f"renderD{128 + card_num}" / "device"
            if render_dir.is_dir():
                util = _read_utilization(render_dir)
                if util is not None:
                    return util

    return 0.0


def _collect_amd_sysfs(identity: DgpuIdentity) -> DedicatedGpuSnapshot:
    resolved = _resolve_amdgpu_device_dir(identity)
    if resolved is None:
        logger.debug("amdgpu sysfs: no se encontró card con nodos VRAM")
        return _detected_only_snapshot(identity)

    device_dir, card_index = resolved
    utilization = _estimate_utilization(identity.drm_card, device_dir)
    mem_used_b, mem_total_b = _read_amdgpu_vram_bytes(device_dir)
    mem_used_mb = _bytes_to_mb_int(mem_used_b)
    mem_total_mb = _bytes_to_mb_int(mem_total_b)

    raw_name = identity.name
    product = read_sysfs_text(device_dir / "product_name")
    if product:
        raw_name = product

    temperature = _read_hwmon_temperature(device_dir)

    return DedicatedGpuSnapshot(
        available=True,
        devices=[
            _make_device(
                name=raw_name,
                index=card_index,
                utilization_percent=utilization,
                memory_used_mb=mem_used_mb,
                memory_total_mb=mem_total_mb,
                temperature_c=temperature,
            )
        ],
        error=None,
    )


def _collect_for_identity(identity: DgpuIdentity) -> DedicatedGpuSnapshot:
    if identity.vendor == "nvidia":
        nvidia = _collect_nvidia_telemetry()
        if nvidia is not None:
            if nvidia.devices and identity.name:
                primary = nvidia.devices[0]
                if primary.name in ("—", "", "NVIDIA GPU"):
                    nvidia.devices[0] = primary.model_copy(
                        update={"name": sanitize_dgpu_commercial_name(identity.name)}
                    )
            return _finalize_snapshot(nvidia)
        return _detected_only_snapshot(identity)

    if identity.vendor == "amd":
        return _finalize_snapshot(_collect_amd_sysfs(identity))

    return _detected_only_snapshot(identity)


def _finalize_snapshot(snapshot: DedicatedGpuSnapshot) -> DedicatedGpuSnapshot:
    """Garantiza payload limpio para pywebview: nombres sanitizados y VRAM numérica."""
    if not snapshot.available or not snapshot.devices:
        return snapshot

    device = snapshot.devices[0]
    used_mb = int(device.memory_used_mb or 0)
    total_mb = int(device.memory_total_mb or 0)
    mem_pct: float | None = None
    if total_mb > 0:
        mem_pct = round(used_mb / total_mb * 100.0, 2)

    snapshot.devices[0] = device.model_copy(
        update={
            "name": sanitize_dgpu_commercial_name(device.name),
            "memory_used_mb": float(used_mb),
            "memory_total_mb": float(total_mb),
            "memory_used_mib": float(used_mb),
            "memory_total_mib": float(total_mb),
            "memory_percent": mem_pct,
        }
    )
    return snapshot


def probe_dedicated_gpu() -> DedicatedGpuSnapshot:
    try:
        identity = discover_dgpu_identity()
        if identity is None:
            return DedicatedGpuSnapshot(
                available=False,
                devices=[],
                error="dgpu_not_detected",
            )
        return _collect_for_identity(identity)
    except Exception as exc:  # noqa: BLE001
        logger.debug("dGPU probe falló: %s", exc)
        return DedicatedGpuSnapshot(
            available=False,
            devices=[],
            error=str(exc),
        )


def dgpu_status_label(snapshot: DedicatedGpuSnapshot | dict) -> str:
    if isinstance(snapshot, dict):
        available = snapshot.get("available", False)
        devices = snapshot.get("devices") or []
        if not available or not devices:
            return "no detectada"
        return str(devices[0].get("name") or "disponible")
    if not snapshot.available or not snapshot.devices:
        return "no detectada"
    return snapshot.devices[0].name
