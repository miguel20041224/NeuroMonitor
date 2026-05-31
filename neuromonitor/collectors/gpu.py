from pathlib import Path

from neuromonitor.collectors.base import MetricCollector
from neuromonitor.models.metrics import GpuDeviceMetrics, GpuMetrics

_DRM_BASE = Path("/sys/class/drm")
_AMD_CARD_CANDIDATES = ("card0", "card1")
_AMD_DEVICE_NAME = "AMD Radeon Graphics"


def _read_sysfs_int(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _read_sysfs_float(path: Path) -> float | None:
    try:
        return float(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _collect_amd_sysfs() -> GpuMetrics | None:
    """Lee telemetría AMD desde sysfs (gpu_busy_percent y VRAM)."""
    for card in _AMD_CARD_CANDIDATES:
        device_dir = _DRM_BASE / card / "device"
        if not device_dir.is_dir():
            continue

        busy_path = device_dir / "gpu_busy_percent"
        if not busy_path.is_file():
            continue

        utilization = _read_sysfs_float(busy_path)
        if utilization is None:
            continue

        mem_used = _read_sysfs_int(device_dir / "mem_info_vram_usage")
        mem_total = _read_sysfs_int(device_dir / "mem_info_vram_total")
        mem_pct: float | None = None
        if mem_used is not None and mem_total and mem_total > 0:
            mem_pct = mem_used / mem_total * 100

        card_index = int(card.removeprefix("card"))
        device = GpuDeviceMetrics(
            index=card_index,
            name=_AMD_DEVICE_NAME,
            utilization_percent=utilization,
            memory_total_bytes=mem_total,
            memory_used_bytes=mem_used,
            memory_percent=mem_pct,
            temperature_c=None,
        )
        return GpuMetrics(available=True, devices=[device])

    return None


class GpuCollector(MetricCollector):
    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._nvml = None

    def _collect_nvidia(self) -> GpuMetrics | None:
        """Fallback NVML para GPUs NVIDIA."""
        try:
            if self._nvml is None:
                import pynvml

                pynvml.nvmlInit()
                self._nvml = pynvml

            nvml = self._nvml
            devices: list[GpuDeviceMetrics] = []
            count = nvml.nvmlDeviceGetCount()
            for index in range(count):
                handle = nvml.nvmlDeviceGetHandleByIndex(index)
                name = nvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8", errors="replace")

                util = nvml.nvmlDeviceGetUtilizationRates(handle)
                mem = nvml.nvmlDeviceGetMemoryInfo(handle)
                temp: float | None = None
                try:
                    temp = float(
                        nvml.nvmlDeviceGetTemperature(
                            handle, nvml.NVML_TEMPERATURE_GPU
                        )
                    )
                except nvml.NVMLError:
                    pass

                mem_total = mem.total
                mem_used = mem.used
                mem_pct = (mem_used / mem_total * 100) if mem_total else None

                devices.append(
                    GpuDeviceMetrics(
                        index=index,
                        name=name,
                        utilization_percent=float(util.gpu),
                        memory_total_bytes=mem_total,
                        memory_used_bytes=mem_used,
                        memory_percent=mem_pct,
                        temperature_c=temp,
                    )
                )

            if not devices:
                return None
            return GpuMetrics(available=True, devices=devices)
        except ImportError:
            return None
        except Exception:  # noqa: BLE001 — drivers/GPU ausentes
            return None

    @staticmethod
    def _degraded_fallback() -> GpuMetrics:
        """Estado pasivo cuando no hay backend GPU compatible."""
        return GpuMetrics(
            available=False,
            devices=[
                GpuDeviceMetrics(
                    index=0,
                    name="—",
                    utilization_percent=0.0,
                )
            ],
            message=(
                "status=degraded; backend=none; "
                "amd_sysfs=unavailable; nvml=unavailable"
            ),
        )

    def collect(self) -> GpuMetrics:
        if not self._enabled:
            return GpuMetrics(
                available=False,
                message="GPU deshabilitado en configuración",
            )

        amd_metrics = _collect_amd_sysfs()
        if amd_metrics is not None:
            return amd_metrics

        nvidia_metrics = self._collect_nvidia()
        if nvidia_metrics is not None:
            return nvidia_metrics

        return self._degraded_fallback()

    def shutdown(self) -> None:
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception:  # noqa: BLE001, S110
                pass
