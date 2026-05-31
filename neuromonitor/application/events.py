from collections.abc import Callable
from threading import Lock

from neuromonitor.models.snapshot import SystemSnapshot

MetricsCallback = Callable[[SystemSnapshot], None]


class MetricsHub:
    """Bus de publicación in-process para conectar servicio y UI de escritorio."""

    def __init__(self) -> None:
        self._subscribers: list[MetricsCallback] = []
        self._lock = Lock()

    def subscribe(self, callback: MetricsCallback) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def publish(self, snapshot: SystemSnapshot) -> None:
        with self._lock:
            subscribers = list(self._subscribers)

        for callback in subscribers:
            callback(snapshot)
