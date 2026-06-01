"""Descubrimiento de GPU dedicada: PCI (lspci/lshw) y correlación con DRM sysfs."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from neuromonitor.telemetry.probes._gpu_name import sanitize_dgpu_commercial_name
from neuromonitor.telemetry.probes._sysfs import (
    _AMD_VENDOR,
    _INTEL_VENDOR,
    _NVIDIA_VENDOR,
    read_sysfs_text,
)

logger = logging.getLogger(__name__)

_DRM_BASE = Path("/sys/class/drm")
_LSPci_TIMEOUT_S = 6.0
_LSHW_TIMEOUT_S = 10.0

_VGA_CLASS_RE = re.compile(r"\b(VGA|3D|Display)\b", re.IGNORECASE)
_PCI_ADDR_RE = re.compile(r"^([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9])", re.IGNORECASE)
_VENDOR_DEVICE_RE = re.compile(r"\[([0-9a-f]{4}):([0-9a-f]{4})\]", re.IGNORECASE)

_INTEGRATED_NAME_HINTS = re.compile(
    r"\b(intel|uhd|iris|xe\s+graphics|hd\s+graphics|"
    r"raphael|renoir|cezanne|picasso|barcelo|vangogh|"
    r"vega\s+\d|lexa|green\s+sardine|gran\s+ridge|"
    r"radeon\s+graphics\b(?!.+(?:rx|pro|xt|series)))",
    re.IGNORECASE,
)
_DISCRETE_AMD_HINTS = re.compile(
    r"\b(radeon\s+rx|radeon\s+pro|rx\s+\d|navi|rdna|polaris|"
    r"vega\s+(?:10|20|56|64|fe)|firepro|instinct)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PciDisplayDevice:
    pci_address: str
    name: str
    vendor_id: str
    device_id: str
    is_likely_integrated: bool


@dataclass(frozen=True)
class DgpuIdentity:
    name: str
    vendor: str  # nvidia | amd | unknown
    pci_address: str | None
    drm_card: str | None


def _normalize_pci(addr: str) -> str:
    text = addr.strip().lower()
    if re.fullmatch(r"[0-9a-f]{2}:[0-9a-f]{2}\.[0-9]", text):
        return f"0000:{text}"
    return text


def _vendor_from_id(vendor_id: str) -> str:
    vid = vendor_id.lower()
    if vid == "10de":
        return "nvidia"
    if vid == "1002":
        return "amd"
    return "unknown"


def _is_integrated_guess(name: str, vendor_id: str) -> bool:
    if vendor_id.lower() == _INTEL_VENDOR.removeprefix("0x"):
        return True
    if _INTEGRATED_NAME_HINTS.search(name):
        return True
    if vendor_id.lower() == "1002" and not _DISCRETE_AMD_HINTS.search(name):
        if re.search(r"\b(radeon\s+graphics|amd\s+graphics)\b", name, re.I):
            return True
    return False


def _extract_commercial_name(line: str) -> str:
    match = re.search(
        r"\]:\s+(.+?)\s+\[(?:10de|1002|8086|1022):[0-9a-f]{4}\]",
        line,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    after = line.split("]:", 1)
    if len(after) > 1:
        tail = after[1].strip()
        bracket = tail.find("[")
        if bracket > 0:
            return tail[:bracket].strip()
        return tail
    return line.strip()


def _parse_lspci_line(line: str) -> PciDisplayDevice | None:
    if not _VGA_CLASS_RE.search(line):
        return None
    addr_match = _PCI_ADDR_RE.match(line)
    vendor_matches = list(_VENDOR_DEVICE_RE.finditer(line))
    if not addr_match or not vendor_matches:
        return None
    vendor_id, device_id = vendor_matches[-1].group(1).lower(), vendor_matches[-1].group(2).lower()
    name = _extract_commercial_name(line)
    pci_address = _normalize_pci(addr_match.group(1))
    return PciDisplayDevice(
        pci_address=pci_address,
        name=name,
        vendor_id=vendor_id,
        device_id=device_id,
        is_likely_integrated=_is_integrated_guess(name, vendor_id),
    )


def _discover_via_lspci() -> list[PciDisplayDevice]:
    lspci = shutil.which("lspci")
    if not lspci:
        return []
    try:
        proc = subprocess.run(
            [lspci, "-nn", "-D"],
            capture_output=True,
            text=True,
            timeout=_LSPci_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("lspci falló: %s", exc)
        return []
    if proc.returncode != 0:
        return []
    devices: list[PciDisplayDevice] = []
    for line in proc.stdout.splitlines():
        parsed = _parse_lspci_line(line)
        if parsed is not None:
            devices.append(parsed)
    return devices


def _discover_via_lshw() -> list[PciDisplayDevice]:
    lshw = shutil.which("lshw")
    if not lshw:
        return []
    try:
        proc = subprocess.run(
            [lshw, "-C", "display"],
            capture_output=True,
            text=True,
            timeout=_LSHW_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("lshw falló: %s", exc)
        return []
    if proc.returncode != 0:
        return []

    devices: list[PciDisplayDevice] = []
    current_bus: str | None = None
    current_product: str | None = None
    current_vendor_id: str | None = None

    def _flush() -> None:
        nonlocal current_bus, current_product, current_vendor_id
        if not current_bus or not current_product:
            current_bus = current_product = current_vendor_id = None
            return
        vendor_id = (current_vendor_id or "0000").lower()
        name = current_product.strip()
        devices.append(
            PciDisplayDevice(
                pci_address=_normalize_pci(current_bus),
                name=name,
                vendor_id=vendor_id,
                device_id="0000",
                is_likely_integrated=_is_integrated_guess(name, vendor_id),
            )
        )
        current_bus = current_product = current_vendor_id = None

    for raw_line in proc.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("*-"):
            _flush()
            continue
        if line.startswith("bus info:"):
            info = line.split(":", 1)[1].strip()
            pci_match = re.search(
                r"pci@([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9])",
                info,
                re.IGNORECASE,
            )
            if pci_match:
                current_bus = pci_match.group(1)
            continue
        if line.startswith("product:"):
            current_product = line.split(":", 1)[1].strip()
            continue
        if line.startswith("vendor:"):
            vendor_match = _VENDOR_DEVICE_RE.search(line)
            if vendor_match:
                current_vendor_id = vendor_match.group(1).lower()
    _flush()
    return devices


@dataclass(frozen=True)
class _DrmCardBinding:
    card_id: str
    device_dir: Path
    vendor: str | None
    pci_address: str | None
    product_name: str | None


def _pci_from_device_symlink(device_dir: Path) -> str | None:
    try:
        resolved = (device_dir).resolve()
    except OSError:
        return None
    match = re.search(
        r"([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9])",
        str(resolved),
        re.IGNORECASE,
    )
    if match:
        return _normalize_pci(match.group(1))
    return None


def _list_drm_bindings() -> list[_DrmCardBinding]:
    bindings: list[_DrmCardBinding] = []
    if not _DRM_BASE.is_dir():
        return bindings
    for entry in sorted(_DRM_BASE.iterdir()):
        name = entry.name
        if not name.startswith("card") or not name[4:].isdigit():
            continue
        device_dir = entry / "device"
        if not device_dir.is_dir():
            continue
        vendor = read_sysfs_text(device_dir / "vendor")
        product = read_sysfs_text(device_dir / "product_name") or read_sysfs_text(
            device_dir / "name"
        )
        bindings.append(
            _DrmCardBinding(
                card_id=name,
                device_dir=device_dir,
                vendor=vendor,
                pci_address=_pci_from_device_symlink(device_dir),
                product_name=product,
            )
        )
    return bindings


def _pick_discrete_pci(devices: list[PciDisplayDevice]) -> PciDisplayDevice | None:
    discrete = [d for d in devices if not d.is_likely_integrated]
    if not discrete:
        nvidia_only = [d for d in devices if d.vendor_id == "10de"]
        if nvidia_only:
            return nvidia_only[-1]
        return None
    nvidia = [d for d in discrete if d.vendor_id == "10de"]
    if nvidia:
        return nvidia[0]
    amd_discrete = [d for d in discrete if d.vendor_id == "1002"]
    if amd_discrete:
        return amd_discrete[0]
    return discrete[0]


def _bind_drm_card(
    pci_device: PciDisplayDevice | None,
    bindings: list[_DrmCardBinding],
) -> _DrmCardBinding | None:
    if pci_device and pci_device.pci_address:
        for binding in bindings:
            if binding.pci_address == pci_device.pci_address:
                return binding
    for binding in bindings:
        vendor = (binding.vendor or "").lower()
        if vendor == _NVIDIA_VENDOR:
            return binding
    if len(bindings) >= 2:
        for binding in bindings:
            vendor = (binding.vendor or "").lower()
            if vendor == _AMD_VENDOR:
                return binding
    return None


def _identity_from_drm(bindings: list[_DrmCardBinding]) -> DgpuIdentity | None:
    for binding in bindings:
        vendor = (binding.vendor or "").lower()
        if vendor != _NVIDIA_VENDOR:
            continue
        name = binding.product_name or "NVIDIA GPU"
        return DgpuIdentity(
            name=sanitize_dgpu_commercial_name(name),
            vendor="nvidia",
            pci_address=binding.pci_address,
            drm_card=binding.card_id,
        )
    if len(bindings) >= 2:
        second = bindings[-1]
        vendor = (second.vendor or "").lower()
        if vendor == _AMD_VENDOR:
            return DgpuIdentity(
                name=sanitize_dgpu_commercial_name(
                    second.product_name or "AMD Radeon GPU"
                ),
                vendor="amd",
                pci_address=second.pci_address,
                drm_card=second.card_id,
            )
    return None


def discover_dgpu_identity() -> DgpuIdentity | None:
    """Detecta la dGPU por bus PCI y la correlaciona con cardN de DRM."""
    bindings = _list_drm_bindings()
    pci_devices = _discover_via_lspci()
    if not pci_devices:
        pci_devices = _discover_via_lshw()

    pci_discrete = _pick_discrete_pci(pci_devices)
    binding = _bind_drm_card(pci_discrete, bindings)

    if pci_discrete:
        vendor = _vendor_from_id(pci_discrete.vendor_id)
        drm_card = binding.card_id if binding else None
        return DgpuIdentity(
            name=sanitize_dgpu_commercial_name(pci_discrete.name),
            vendor=vendor,
            pci_address=pci_discrete.pci_address,
            drm_card=drm_card,
        )

    fallback = _identity_from_drm(bindings)
    if fallback is not None:
        return fallback

    return None
