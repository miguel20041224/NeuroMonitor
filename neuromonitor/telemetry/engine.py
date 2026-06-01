"""Motor de telemetría: orquestación adaptativa y snapshot unificado."""

from __future__ import annotations

import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from neuromonitor.telemetry.discovery import (
    HardwareMap,
    discover_hardware,
    log_hardware_discovery,
)
from neuromonitor.telemetry.models import TelemetryPayload
from neuromonitor.telemetry.probes import (
    probe_dedicated_gpu,
    probe_disks,
    probe_integrated_gpu,
    probe_processes,
    probe_ram,
)

logger = logging.getLogger(__name__)

_engine: "TelemetryEngine | None" = None


class TelemetryEngine:
    """Bridge de telemetría adaptativa al hardware detectado en arranque."""

    def __init__(self, *, run_discovery: bool = True) -> None:
        self._hostname = socket.gethostname()
        self._hardware: HardwareMap | None = None
        if run_discovery:
            self._hardware = discover_hardware()
            log_hardware_discovery(self._hardware)

    @property
    def hardware(self) -> HardwareMap | None:
        return self._hardware

    def collect_snapshot(self) -> TelemetryPayload:
        ram = probe_ram()
        disks = probe_disks()
        integrated = probe_integrated_gpu()
        dedicated = probe_dedicated_gpu()
        processes = probe_processes()

        return TelemetryPayload(
            hostname=self._hostname,
            collected_at=round(time.time(), 3),
            memory=ram,
            disks=disks,
            integrated_gpu=integrated,
            dedicated_gpu=dedicated,
            processes=processes,
        )

    def collect_snapshot_parallel(self) -> TelemetryPayload:
        """GPUs y procesos en paralelo; RAM/disco secuencial ligero."""
        ram = probe_ram()
        disks = probe_disks()
        integrated = probe_integrated_gpu()
        dedicated = probe_dedicated_gpu()
        processes: list = []

        try:
            with ThreadPoolExecutor(
                max_workers=3,
                thread_name_prefix="neuromonitor-telemetry",
            ) as pool:
                igpu_future = pool.submit(probe_integrated_gpu)
                dgpu_future = pool.submit(probe_dedicated_gpu)
                proc_future = pool.submit(probe_processes)
                integrated = igpu_future.result()
                dedicated = dgpu_future.result()
                processes = proc_future.result()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Pool telemetría degradado: %s", exc)
            integrated = probe_integrated_gpu()
            dedicated = probe_dedicated_gpu()
            processes = probe_processes()

        return TelemetryPayload(
            hostname=self._hostname,
            collected_at=round(time.time(), 3),
            memory=ram,
            disks=disks,
            integrated_gpu=integrated,
            dedicated_gpu=dedicated,
            processes=processes,
        )

    def get_snapshot_dict(self) -> dict[str, Any]:
        return self.collect_snapshot_parallel().to_bridge_dict()


def get_engine(*, run_discovery: bool = False) -> TelemetryEngine:
    global _engine
    if _engine is None:
        _engine = TelemetryEngine(run_discovery=run_discovery)
    return _engine


def get_gpu_and_processes() -> dict[str, Any]:
    """Punto de entrada RPC: snapshot unificado en tiempo real."""
    return get_engine().get_snapshot_dict()
