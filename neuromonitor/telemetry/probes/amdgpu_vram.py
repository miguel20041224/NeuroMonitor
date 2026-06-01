"""Mapeo de VRAM dedicada por PID en GPUs AMD (amdgpu) bajo Linux."""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from neuromonitor.telemetry.probes._dgpu_discovery import discover_dgpu_identity
from neuromonitor.telemetry.probes.dgpu import _resolve_amdgpu_device_dir

logger = logging.getLogger(__name__)

_DRM_BASE = Path("/sys/class/drm")
_DEBUG_DRI = Path("/sys/kernel/debug/dri")
_BYTES_PER_MB = 1024 * 1024
_UMR_TIMEOUT_S = 8.0

# amdgpu_gpm_clients: pid, client id, vram, sdma, ssid, name
_GPM_CLIENT_RE = re.compile(
    r"^\s*(\d+)\s+(?:0x[0-9a-fA-F]+\s+)?(\d+)\s+\d+\s+",
    re.MULTILINE,
)
# drm clients sysfs: pid comm vram [gtt]
_DRM_CLIENT_RE = re.compile(
    r"^\s*(\d+)\s+\S+\s+(\d+)",
    re.MULTILINE,
)
# umr -t: líneas con pid y bytes de VRAM (varía según versión)
_UMR_PID_VRAM_RE = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+(\d+)",
    re.MULTILINE,
)
_FDINFO_AMDGPU_SIG = "drm-driver: amdgpu"
_FDINFO_VRAM_RE = re.compile(r"^drm-memory-vram:\s*(\d+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class AmdVramMapResult:
    """VRAM por PID en megabytes y fuente usada."""

    by_pid_mb: dict[int, float]
    source: str


def _bytes_to_mb(value: int) -> float:
    if value <= 0:
        return 0.0
    return round(value / _BYTES_PER_MB, 2)


def _merge_vram_maps(
    target: dict[int, float],
    incoming: dict[int, float],
) -> None:
    for pid, vram_mb in incoming.items():
        if vram_mb <= 0:
            continue
        current = target.get(pid, 0.0)
        if vram_mb > current:
            target[pid] = vram_mb


def _resolve_amd_card_index() -> int | None:
    identity = discover_dgpu_identity()
    if identity is None or identity.vendor != "amd":
        return None
    resolved = _resolve_amdgpu_device_dir(identity)
    if resolved is None:
        if identity.drm_card:
            try:
                return int(identity.drm_card.removeprefix("card"))
            except ValueError:
                return None
        return None
    _, card_index = resolved
    return card_index


def _parse_gpm_clients(text: str) -> dict[int, float]:
    result: dict[int, float] = {}
    for match in _GPM_CLIENT_RE.finditer(text):
        pid = int(match.group(1))
        vram_bytes = int(match.group(2))
        _merge_vram_maps(result, {pid: _bytes_to_mb(vram_bytes)})
    return result


def _parse_drm_clients(text: str) -> dict[int, float]:
    result: dict[int, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("pid"):
            continue
        match = _DRM_CLIENT_RE.match(line)
        if not match:
            continue
        pid = int(match.group(1))
        vram_bytes = int(match.group(2))
        _merge_vram_maps(result, {pid: _bytes_to_mb(vram_bytes)})
    return result


def _read_gpm_clients(card_index: int) -> dict[int, float]:
    path = _DEBUG_DRI / str(card_index) / "amdgpu_gpm_clients"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.debug("amdgpu_gpm_clients no accesible (%s): %s", path, exc)
        return {}
    parsed = _parse_gpm_clients(text)
    if parsed:
        logger.debug("VRAM por PID desde %s (%d procesos)", path, len(parsed))
    return parsed


def _read_drm_clients_sysfs(card_index: int) -> dict[int, float]:
    path = _DRM_BASE / f"card{card_index}" / "device" / "drm" / f"card{card_index}" / "clients"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.debug("drm clients no accesible (%s): %s", path, exc)
        return {}
    parsed = _parse_drm_clients(text)
    if parsed:
        logger.debug("VRAM por PID desde %s (%d procesos)", path, len(parsed))
    return parsed


def _parse_umr_table(text: str) -> dict[int, float]:
    result: dict[int, float] = {}
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if "process" in lower and "table" in lower:
            in_table = True
            continue
        if not in_table:
            continue
        if lower.startswith("pid") or stripped.startswith("=="):
            continue
        match = _UMR_PID_VRAM_RE.match(stripped)
        if not match:
            continue
        pid = int(match.group(1))
        vram_bytes = int(match.group(2))
        _merge_vram_maps(result, {pid: _bytes_to_mb(vram_bytes)})
    if not result:
        for match in _UMR_PID_VRAM_RE.finditer(text):
            pid = int(match.group(1))
            vram_bytes = int(match.group(2))
            _merge_vram_maps(result, {pid: _bytes_to_mb(vram_bytes)})
    return result


def _read_umr_process_table() -> dict[int, float]:
    try:
        proc = subprocess.run(
            ["umr", "-t"],
            capture_output=True,
            text=True,
            timeout=_UMR_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("umr -t no disponible: %s", exc)
        return {}
    if proc.returncode != 0 and not proc.stdout.strip():
        logger.debug("umr -t exit %s: %s", proc.returncode, proc.stderr.strip())
        return {}
    parsed = _parse_umr_table(proc.stdout)
    if parsed:
        logger.debug("VRAM por PID desde umr -t (%d procesos)", len(parsed))
    return parsed


def _pid_from_proc_fdinfo_path(fdinfo_path: Path) -> int | None:
    parts = fdinfo_path.parts
    try:
        proc_idx = parts.index("proc")
        return int(parts[proc_idx + 1])
    except (ValueError, IndexError):
        return None


def _vram_bytes_from_fdinfo_text(text: str) -> int:
    if _FDINFO_AMDGPU_SIG not in text:
        return 0
    total = 0
    for match in _FDINFO_VRAM_RE.finditer(text):
        total += int(match.group(1))
    return total


def _vram_from_proc_fdinfo() -> dict[int, float]:
    """Escanea /proc/[0-9]*/fdinfo/* y agrega VRAM amdgpu por PID (bytes → MB)."""
    result: dict[int, float] = {}
    proc_root = Path("/proc")
    try:
        fdinfo_paths = proc_root.glob("[0-9]*/fdinfo/*")
    except OSError:
        return result

    vram_bytes_by_pid: dict[int, int] = {}
    for fdinfo_file in fdinfo_paths:
        if not fdinfo_file.is_file():
            continue
        pid = _pid_from_proc_fdinfo_path(fdinfo_file)
        if pid is None:
            continue
        try:
            text = fdinfo_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        file_vram = _vram_bytes_from_fdinfo_text(text)
        if file_vram <= 0:
            continue
        vram_bytes_by_pid[pid] = vram_bytes_by_pid.get(pid, 0) + file_vram

    for pid, vram_bytes in vram_bytes_by_pid.items():
        _merge_vram_maps(result, {pid: _bytes_to_mb(vram_bytes)})
    if result:
        logger.debug("VRAM por PID desde /proc/*/fdinfo (%d procesos)", len(result))
    return result


def map_amd_vram_by_pid(*, card_index: int | None = None) -> AmdVramMapResult:
    """Mapea VRAM dedicada (MB) por PID; fdinfo (/proc) es la fuente principal en amdgpu."""
    resolved_index = card_index if card_index is not None else _resolve_amd_card_index()
    by_pid: dict[int, float] = {}
    source = "none"

    fdinfo_map = _vram_from_proc_fdinfo()
    if fdinfo_map:
        _merge_vram_maps(by_pid, fdinfo_map)
        source = "fdinfo"

    if resolved_index is not None:
        for reader, label in (
            (_read_gpm_clients(resolved_index), "amdgpu_gpm_clients"),
            (_read_drm_clients_sysfs(resolved_index), "drm_clients"),
        ):
            if reader:
                _merge_vram_maps(by_pid, reader)
                if source == "none":
                    source = label

    if not by_pid:
        umr_map = _read_umr_process_table()
        if umr_map:
            _merge_vram_maps(by_pid, umr_map)
            source = "umr"

    return AmdVramMapResult(by_pid_mb=by_pid, source=source)
