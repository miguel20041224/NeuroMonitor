"""Modelos del payload unificado de telemetría."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RamSnapshot(BaseModel):
    total_gb: float = 0.0
    available_gb: float = 0.0
    used_gb: float = 0.0
    percent: float = 0.0


class DiskSnapshot(BaseModel):
    mountpoint: str
    total_gb: float = 0.0
    used_gb: float = 0.0
    percent: float = 0.0


class IntegratedGpuSnapshot(BaseModel):
    available: bool = False
    name: str | None = None
    utilization_percent: float | None = None
    source: str = "none"
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None
    memory_percent: float | None = None
    error: str | None = None


class DedicatedGpuDeviceSnapshot(BaseModel):
    index: int = 0
    name: str = "GPU Dedicada"
    utilization_percent: float = 0.0
    memory_used_mb: float | None = None
    memory_total_mb: float | None = None
    memory_total_mib: float | None = None
    memory_used_mib: float | None = None
    temperature_c: float | None = None
    memory_percent: float | None = None


class DedicatedGpuSnapshot(BaseModel):
    available: bool = False
    devices: list[DedicatedGpuDeviceSnapshot] = Field(default_factory=list)
    error: str | None = None

    def bridge_dict(self) -> dict[str, Any]:
        """Serialización segura para pywebview: sin N/D, nulos ni guiones en VRAM."""
        payload = self.model_dump(mode="json")
        if not payload.get("available") or not payload.get("devices"):
            return payload
        primary = dict(payload["devices"][0])
        used = int(primary.get("memory_used_mb") or primary.get("memory_used_mib") or 0)
        total = int(primary.get("memory_total_mb") or primary.get("memory_total_mib") or 0)
        name = str(primary.get("name") or "GPU Dedicada").strip()
        if name in {"—", "-", "N/D", "N/A"}:
            name = "GPU Dedicada"
        mem_pct = primary.get("memory_percent")
        if mem_pct is None and total > 0:
            mem_pct = round(used / total * 100.0, 2)
        primary.update(
            {
                "name": name,
                "memory_used_mb": used,
                "memory_total_mb": total,
                "memory_used_mib": used,
                "memory_total_mib": total,
                "memory_percent": mem_pct,
            }
        )
        payload["devices"] = [primary, *payload["devices"][1:]]
        return payload


class ProcessSnapshot(BaseModel):
    pid: int
    name: str
    cpu_percent: float = 0.0
    memory_rss_mb: float = 0.0
    vram_mb: float | None = None


class TelemetryPayload(BaseModel):
    hostname: str
    collected_at: float
    memory: RamSnapshot
    disks: list[DiskSnapshot] = Field(default_factory=list)
    integrated_gpu: IntegratedGpuSnapshot
    dedicated_gpu: DedicatedGpuSnapshot
    processes: list[ProcessSnapshot] = Field(default_factory=list)

    def to_bridge_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["dedicated_gpu"] = self.dedicated_gpu.bridge_dict()
        return data
