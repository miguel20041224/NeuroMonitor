import socket

from neuromonitor.collectors import (
    CpuCollector,
    DiskCollector,
    GpuCollector,
    MemoryCollector,
)
from neuromonitor.config import Settings
from neuromonitor.models.snapshot import SystemSnapshot


class MonitorService:
    """Orquesta collectors y produce snapshots para la aplicación de escritorio."""

    def __init__(self, settings: Settings | None = None) -> None:
        from neuromonitor.config import get_settings

        self._settings = settings or get_settings()
        self._cpu = CpuCollector(sample_interval=0.05)
        self._memory = MemoryCollector()
        self._disk = DiskCollector()
        self._gpu = GpuCollector(enabled=self._settings.enable_gpu)
        self._hostname = socket.gethostname()

    def capture_snapshot(self) -> SystemSnapshot:
        return SystemSnapshot(
            hostname=self._hostname,
            cpu=self._cpu.collect(),
            memory=self._memory.collect(),
            disk=self._disk.collect(),
            gpu=self._gpu.collect(),
        )

    def shutdown(self) -> None:
        self._gpu.shutdown()
