from datetime import datetime, timezone

from pydantic import BaseModel, Field

from neuromonitor.models.metrics import (
    CpuMetrics,
    DiskMetrics,
    GpuMetrics,
    MemoryMetrics,
)


class SystemSnapshot(BaseModel):
    """Instantánea unificada consumida por la UI de escritorio."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    hostname: str
    cpu: CpuMetrics
    memory: MemoryMetrics
    disk: DiskMetrics
    gpu: GpuMetrics

    def model_dump_json_api(self) -> dict:
        return self.model_dump(mode="json")
