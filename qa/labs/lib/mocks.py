"""Mocks de psutil/NVML para laboratorios (solo QA)."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch


@dataclass
class MockScenario:
    name: str
    patches: dict[str, Any]


def normal_psutil() -> MockScenario:
    return MockScenario(
        name="normal",
        patches={
            "psutil.cpu_percent": lambda interval=None, percpu=False: (
                [25.0, 30.0] if percpu else 27.5
            ),
            "psutil.cpu_freq": lambda: SimpleNamespace(current=3200.0),
            "psutil.cpu_count": lambda logical=True: 2 if logical else 1,
            "psutil.virtual_memory": lambda: SimpleNamespace(
                total=16_000_000_000,
                used=8_000_000_000,
                available=8_000_000_000,
                percent=50.0,
            ),
            "psutil.swap_memory": lambda: SimpleNamespace(
                total=4_000_000_000,
                used=0,
                percent=0.0,
            ),
            "psutil.disk_partitions": lambda all=False: [
                SimpleNamespace(
                    device="/dev/sda1",
                    mountpoint="/",
                    fstype="ext4",
                )
            ],
            "psutil.disk_usage": lambda path: SimpleNamespace(
                total=100_000_000_000,
                used=50_000_000_000,
                free=50_000_000_000,
                percent=50.0,
            ),
            "psutil.disk_io_counters": lambda: SimpleNamespace(
                read_bytes=1_000_000,
                write_bytes=500_000,
            ),
        },
    )


def corrupt_cpu_percent() -> MockScenario:
    scenario = normal_psutil()
    scenario.name = "cpu_percent_101"
    scenario.patches["psutil.cpu_percent"] = lambda interval=None, percpu=False: (
        [101.5, 50.0] if percpu else 101.5
    )
    return scenario


def disk_io_reset() -> MockScenario:
    """Simula reset de contadores entre muestras."""
    scenario = normal_psutil()
    scenario.name = "disk_io_reset"
    state = {"call": 0}

    def io_counters() -> SimpleNamespace:
        state["call"] += 1
        if state["call"] == 1:
            return SimpleNamespace(read_bytes=10_000_000, write_bytes=5_000_000)
        return SimpleNamespace(read_bytes=100, write_bytes=50)

    scenario.patches["psutil.disk_io_counters"] = io_counters
    return scenario


def counting_psutil() -> tuple[MockScenario, dict[str, int]]:
    """
    Escenario normal con contadores de invocaciones psutil (instrumentación QA).
    Retorna (scenario, counters) con claves: cpu_percent, disk_io_counters, virtual_memory.
    """
    scenario = normal_psutil()
    scenario.name = "counting"
    counters = {"cpu_percent": 0, "disk_io_counters": 0, "virtual_memory": 0}

    base_cpu = scenario.patches["psutil.cpu_percent"]
    base_io = scenario.patches["psutil.disk_io_counters"]
    base_mem = scenario.patches["psutil.virtual_memory"]

    def cpu_percent(interval=None, percpu=False):  # noqa: ANN001
        counters["cpu_percent"] += 1
        return base_cpu(interval=interval, percpu=percpu)

    def disk_io_counters():
        counters["disk_io_counters"] += 1
        return base_io()

    def virtual_memory():
        counters["virtual_memory"] += 1
        return base_mem()

    scenario.patches["psutil.cpu_percent"] = cpu_percent
    scenario.patches["psutil.disk_io_counters"] = disk_io_counters
    scenario.patches["psutil.virtual_memory"] = virtual_memory
    return scenario, counters


def apply_scenario(scenario: MockScenario):
    return patch.multiple("psutil", **scenario.patches)
