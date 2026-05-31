"""Buffer circular thread-safe para el historial de snapshots de métricas."""

from __future__ import annotations

from collections import deque
from threading import Lock

from neuromonitor.models.snapshot import SystemSnapshot


class HistoryBuffer:
    """Cola acotada de snapshots compartida entre el hilo de polling y la UI.

    El colector de métricas escribe cada muestra mientras la UI o el bridge
    leen el historial para gráficos y consultas RPC. El ``Lock`` evita
    condiciones de carrera entre lecturas concurrentes y ``append``.
    """

    def __init__(self, max_size: int = 300) -> None:
        if max_size < 1:
            raise ValueError("max_size debe ser >= 1")
        self._max_size = max_size
        self._buffer: deque[SystemSnapshot] = deque(maxlen=max_size)
        self._lock = Lock()

    @property
    def max_size(self) -> int:
        return self._max_size

    def append(self, snapshot: SystemSnapshot) -> None:
        """Añade una instantánea al final del buffer (descarta la más antigua si está lleno)."""
        with self._lock:
            self._buffer.append(snapshot)

    def get_all(self) -> list[SystemSnapshot]:
        """Devuelve una copia del historial actual, ordenada de más antigua a más reciente."""
        with self._lock:
            return list(self._buffer)

    def clear(self) -> None:
        """Vacía el buffer (p. ej. al cambiar intervalo o reiniciar sesión)."""
        with self._lock:
            self._buffer.clear()
