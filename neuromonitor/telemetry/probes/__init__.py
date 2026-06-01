"""Probes de telemetría por dominio."""

from neuromonitor.telemetry.probes.amdgpu_vram import map_amd_vram_by_pid
from neuromonitor.telemetry.probes.disks import probe_disks
from neuromonitor.telemetry.probes.dgpu import probe_dedicated_gpu
from neuromonitor.telemetry.probes.igpu import probe_integrated_gpu
from neuromonitor.telemetry.probes.processes import probe_processes
from neuromonitor.telemetry.probes.ram import probe_ram

__all__ = [
    "probe_ram",
    "probe_disks",
    "probe_integrated_gpu",
    "probe_dedicated_gpu",
    "probe_processes",
    "map_amd_vram_by_pid",
]
