import logging
import threading
import time
from collections.abc import Callable

from neuromonitor.application.events import MetricsCallback, MetricsHub
from neuromonitor.config import Settings, get_settings
from neuromonitor.models.snapshot import SystemSnapshot
from neuromonitor.services.monitor_service import MonitorService

logger = logging.getLogger(__name__)


class NeuroMonitorApplication:
    """Aplicación de escritorio: orquesta polling y entrega snapshots a la UI."""

    def __init__(
        self,
        settings: Settings | None = None,
        service: MonitorService | None = None,
        hub: MetricsHub | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._service = service or MonitorService(self._settings)
        self._hub = hub or MetricsHub()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None

    @property
    def hub(self) -> MetricsHub:
        return self._hub

    def subscribe(self, callback: MetricsCallback) -> Callable[[], None]:
        return self._hub.subscribe(callback)

    def capture_snapshot(self) -> SystemSnapshot:
        return self._service.capture_snapshot()

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._poll_loop,
            name="neuromonitor-metrics",
            daemon=True,
        )
        self._worker.start()
        logger.info(
            "Monitor iniciado (intervalo=%sms)",
            self._settings.poll_interval_ms,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=self._settings.poll_interval_ms / 1000 + 2)
        self._service.shutdown()
        logger.info("Monitor detenido")

    def run_forever(self) -> None:
        """Inicia el polling y bloquea hasta Ctrl+C o stop()."""
        self.start()
        try:
            while not self._stop_event.is_set():
                time.sleep(0.25)
        except KeyboardInterrupt:
            logger.info("Interrupción recibida")
        finally:
            self.stop()

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            started = time.perf_counter()
            try:
                snapshot = self._service.capture_snapshot()
                self._hub.publish(snapshot)
            except Exception:
                logger.exception("Error capturando métricas")
            elapsed = time.perf_counter() - started
            interval_s = self._settings.poll_interval_ms / 1000.0
            self._stop_event.wait(max(0.0, interval_s - elapsed))
