import json
import sys

from neuromonitor.models.snapshot import SystemSnapshot


class ConsolePresenter:
    """Presentador mínimo para validar el flujo de métricas sin UI gráfica."""

    def __init__(self, stream=None) -> None:
        self._stream = stream or sys.stdout

    def on_snapshot(self, snapshot: SystemSnapshot) -> None:
        payload = snapshot.model_dump(mode="json")
        cpu = payload["cpu"]["percent"]
        memory = payload["memory"]["percent"]
        disk_count = len(payload["disk"]["partitions"])
        gpu = payload["gpu"]
        gpu_label = "N/A"
        if gpu.get("available") and gpu.get("devices"):
            util = gpu["devices"][0].get("utilization_percent")
            gpu_label = f"{util:.1f}%" if util is not None else "activa"
        elif gpu.get("message"):
            gpu_label = gpu["message"]

        summary = (
            f"[{payload['timestamp']}] "
            f"CPU {cpu:.1f}% | RAM {memory:.1f}% | "
            f"Disco ({disk_count} vol.) | GPU {gpu_label}"
        )
        print(summary, file=self._stream, flush=True)

    def on_snapshot_json(self, snapshot: SystemSnapshot) -> None:
        print(
            json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False),
            file=self._stream,
            flush=True,
        )
