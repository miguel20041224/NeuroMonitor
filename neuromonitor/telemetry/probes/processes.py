"""Sondeo de procesos activos vía psutil con filtro inteligente y VRAM AMD por PID."""

from __future__ import annotations

import logging
import time

import psutil

from neuromonitor.telemetry.models import ProcessSnapshot
from neuromonitor.telemetry.probes.amdgpu_vram import map_amd_vram_by_pid

logger = logging.getLogger(__name__)

_CPU_SAMPLE_S = 0.08
_MIN_RSS_MB = 5.0
_MIN_CPU_PERCENT = 0.5


def _passes_filter(cpu_percent: float, rss_mb: float, *, vram_mb: float | None = None) -> bool:
    if vram_mb is not None and vram_mb > 0:
        return True
    return rss_mb >= _MIN_RSS_MB or cpu_percent >= _MIN_CPU_PERCENT


def _sort_processes(processes: list[ProcessSnapshot]) -> list[ProcessSnapshot]:
    with_vram = [item for item in processes if (item.vram_mb or 0) > 0]
    without_vram = [item for item in processes if (item.vram_mb or 0) <= 0]
    with_vram.sort(key=lambda item: item.vram_mb or 0, reverse=True)
    without_vram.sort(key=lambda item: item.cpu_percent, reverse=True)
    return with_vram + without_vram


def _snapshot_from_process(
    proc: psutil.Process,
    *,
    vram_mb: float | None,
) -> ProcessSnapshot | None:
    try:
        with proc.oneshot():
            pid = proc.pid
            name = proc.info.get("name") if proc.info else None
            if not name:
                name = proc.name()
            mem_info = proc.info.get("memory_info") if proc.info else None
            if mem_info is None:
                mem_info = proc.memory_info()
            rss_mb = float(mem_info.rss) / (1024 * 1024)
            cpu_percent = float(proc.cpu_percent(interval=None))
    except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, OSError):
        return None
    except (TypeError, ValueError, AttributeError) as exc:
        logger.debug("proceso omitido: %s", exc)
        return None

    if not _passes_filter(cpu_percent, rss_mb, vram_mb=vram_mb):
        return None

    return ProcessSnapshot(
        pid=int(pid),
        name=str(name),
        cpu_percent=round(cpu_percent, 2),
        memory_rss_mb=round(rss_mb, 2),
        vram_mb=vram_mb if vram_mb is not None and vram_mb > 0 else None,
    )


def probe_processes() -> list[ProcessSnapshot]:
    vram_result = map_amd_vram_by_pid()
    vram_by_pid = vram_result.by_pid_mb
    if vram_by_pid:
        logger.debug("VRAM AMD mapeada (%s): %d PIDs", vram_result.source, len(vram_by_pid))

    processes: list[ProcessSnapshot] = []
    try:
        candidates = list(
            psutil.process_iter(["pid", "name", "memory_info"], ad_value=None)
        )
    except (OSError, RuntimeError) as exc:
        logger.debug("process_iter falló: %s", exc)
        return processes

    for proc in candidates:
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, OSError):
            continue

    time.sleep(_CPU_SAMPLE_S)

    seen_pids: set[int] = set()
    for proc in candidates:
        vram_mb = vram_by_pid.get(proc.pid)
        snapshot = _snapshot_from_process(proc, vram_mb=vram_mb)
        if snapshot is None:
            continue
        processes.append(snapshot)
        seen_pids.add(snapshot.pid)

    for pid, vram_mb in vram_by_pid.items():
        if vram_mb <= 0 or pid in seen_pids:
            continue
        try:
            proc = psutil.Process(pid)
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, OSError):
            continue
        snapshot = _snapshot_from_process(proc, vram_mb=vram_mb)
        if snapshot is None:
            snapshot = ProcessSnapshot(
                pid=int(pid),
                name=str(proc.name()),
                cpu_percent=0.0,
                memory_rss_mb=0.0,
                vram_mb=round(vram_mb, 2),
            )
        processes.append(snapshot)
        seen_pids.add(pid)

    return _sort_processes(processes)
