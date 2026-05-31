from enum import StrEnum

from pydantic import BaseModel, Field


class MetricKind(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    GPU = "gpu"


class CpuCoreMetrics(BaseModel):
    core_id: int
    percent: float = Field(ge=0, le=100)


class CpuMetrics(BaseModel):
    kind: MetricKind = MetricKind.CPU
    percent: float = Field(ge=0, le=100)
    per_core: list[CpuCoreMetrics] = Field(default_factory=list)
    frequency_mhz: float | None = None
    load_avg_1m: float | None = None
    logical_cores: int
    physical_cores: int | None = None
    message: str | None = None


class MemoryMetrics(BaseModel):
    kind: MetricKind = MetricKind.MEMORY
    total_bytes: int = Field(ge=0)
    used_bytes: int = Field(ge=0)
    available_bytes: int = Field(ge=0)
    percent: float = Field(ge=0, le=100)
    swap_total_bytes: int = Field(ge=0)
    swap_used_bytes: int = Field(ge=0)
    swap_percent: float = Field(ge=0, le=100)
    message: str | None = None


class DiskPartitionMetrics(BaseModel):
    device: str
    mountpoint: str
    fstype: str
    total_bytes: int = Field(ge=0)
    used_bytes: int = Field(ge=0)
    free_bytes: int = Field(ge=0)
    percent: float = Field(ge=0, le=100)


class DiskMetrics(BaseModel):
    kind: MetricKind = MetricKind.DISK
    partitions: list[DiskPartitionMetrics] = Field(default_factory=list)
    read_bytes_per_sec: float | None = None
    write_bytes_per_sec: float | None = None
    message: str | None = None


class GpuDeviceMetrics(BaseModel):
    index: int
    name: str
    utilization_percent: float | None = Field(default=None, ge=0, le=100)
    memory_total_bytes: int | None = Field(default=None, ge=0)
    memory_used_bytes: int | None = Field(default=None, ge=0)
    memory_percent: float | None = Field(default=None, ge=0, le=100)
    temperature_c: float | None = None


class GpuMetrics(BaseModel):
    kind: MetricKind = MetricKind.GPU
    available: bool
    devices: list[GpuDeviceMetrics] = Field(default_factory=list)
    message: str | None = None
