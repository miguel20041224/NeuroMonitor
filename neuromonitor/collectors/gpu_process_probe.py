"""Reexport del módulo de telemetría (compatibilidad con imports legacy)."""

from neuromonitor.telemetry.engine import get_gpu_and_processes
from neuromonitor.telemetry.probes.amdgpu_vram import map_amd_vram_by_pid
from neuromonitor.telemetry.probes.dgpu import probe_dedicated_gpu as detect_dedicated_gpu
from neuromonitor.telemetry.probes.igpu import probe_integrated_gpu as detect_integrated_gpu
from neuromonitor.telemetry.probes.processes import probe_processes as collect_active_processes

collect_gpu_and_processes = get_gpu_and_processes

__all__ = [
    "collect_gpu_and_processes",
    "get_gpu_and_processes",
    "collect_active_processes",
    "detect_integrated_gpu",
    "detect_dedicated_gpu",
    "map_amd_vram_by_pid",
]
