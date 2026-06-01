"""Autodescubrimiento de hardware en fase de arranque."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from neuromonitor.telemetry.probes._dgpu_discovery import discover_dgpu_identity
from neuromonitor.telemetry.probes.disks import probe_disks
from neuromonitor.telemetry.probes.igpu import probe_integrated_gpu
from neuromonitor.telemetry.probes.ram import probe_ram

logger = logging.getLogger(__name__)

_DRM_BASE = Path("/sys/class/drm")
_NVIDIA_VENDOR = "0x10de"


@dataclass
class HardwareMap:
    ram_total_gb: float = 0.0
    ram_available: bool = False
    disk_count: int = 0
    igpu_available: bool = False
    igpu_name: str | None = None
    igpu_status: str = "no detectada"
    dgpu_available: bool = False
    dgpu_name: str | None = None
    dgpu_status: str = "no detectada"
    nvidia_smi_present: bool = False
    component_count: int = 0
    extras: dict[str, object] = field(default_factory=dict)


def _igpu_status_label(available: bool, name: str | None) -> str:
    if not available:
        return "no detectada"
    return name or "disponible"


def _nvidia_drm_present() -> bool:
    try:
        if not _DRM_BASE.is_dir():
            return False
        for card in _DRM_BASE.iterdir():
            if not card.name.startswith("card"):
                continue
            vendor_path = card / "device" / "vendor"
            try:
                vendor = vendor_path.read_text(encoding="utf-8").strip().lower()
            except OSError:
                continue
            if vendor == _NVIDIA_VENDOR:
                return True
    except OSError:
        return False
    return False


def _probe_dgpu_discovery() -> tuple[bool, str]:
    """Detección ligera por PCI/DRM; no ejecuta nvidia-smi en arranque."""
    try:
        identity = discover_dgpu_identity()
        if identity is not None:
            return True, identity.name
    except Exception as exc:  # noqa: BLE001
        logger.debug("Discovery dGPU PCI: %s", exc)
    if _nvidia_drm_present():
        return True, "NVIDIA (driver DRM)"
    return False, "no detectada"


def discover_hardware() -> HardwareMap:
    """Inspecciona el sistema y construye el mapa de componentes disponibles."""
    hw = HardwareMap()
    hw.nvidia_smi_present = shutil.which("nvidia-smi") is not None

    try:
        ram = probe_ram()
        hw.ram_available = ram.total_gb > 0
        hw.ram_total_gb = ram.total_gb
    except Exception as exc:  # noqa: BLE001
        logger.debug("Discovery RAM: %s", exc)

    try:
        disks = probe_disks()
        hw.disk_count = len(disks)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Discovery discos: %s", exc)

    try:
        igpu = probe_integrated_gpu()
        hw.igpu_available = igpu.available
        hw.igpu_name = igpu.name
        hw.igpu_status = _igpu_status_label(igpu.available, igpu.name)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Discovery iGPU: %s", exc)

    try:
        dgpu_available, dgpu_status = _probe_dgpu_discovery()
        hw.dgpu_available = dgpu_available
        hw.dgpu_status = dgpu_status
        if dgpu_available:
            hw.dgpu_name = dgpu_status
    except Exception as exc:  # noqa: BLE001
        logger.debug("Discovery dGPU: %s", exc)

    hw.component_count = sum(
        (
            1 if hw.ram_available else 0,
            hw.disk_count,
            1 if hw.igpu_available else 0,
            1 if hw.dgpu_available else 0,
        )
    )

    try:
        hw.extras["logical_cpus"] = psutil.cpu_count(logical=True)
    except (OSError, RuntimeError):
        hw.extras["logical_cpus"] = None

    return hw


def log_hardware_discovery(hw: HardwareMap) -> None:
    """Imprime log estructurado de confirmación en consola."""
    ram_label = f"{hw.ram_total_gb:.1f}GB" if hw.ram_available else "no detectada"
    message = (
        f"Ok, detectados {hw.component_count} componentes: "
        f"RAM ({ram_label}), {hw.disk_count} Discos activos, "
        f"iGPU ({hw.igpu_status}), dGPU ({hw.dgpu_status})"
    )
    print(message, flush=True)
    logger.info(message)
