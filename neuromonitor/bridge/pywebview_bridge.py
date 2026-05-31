"""API RPC expuesta a la ventana pywebview (js_api)."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from neuromonitor.application.app import NeuroMonitorApplication
from neuromonitor.config.settings import Settings
from neuromonitor.models.snapshot import SystemSnapshot
from neuromonitor.services.history_buffer import HistoryBuffer

logger = logging.getLogger(__name__)

_MAX_HISTORY_LIMIT = 500

_SETTINGS_ALLOWLIST = frozenset({"poll_interval_ms", "enable_gpu", "app_name"})

_ERR_INVALID_SETTINGS = "ERR_INVALID_SETTINGS"
_ERR_INTERNAL = "ERR_INTERNAL"
_MSG_INVALID_SETTINGS = "Configuración inválida"
_MSG_INTERNAL = "Error interno al actualizar configuración"


class NeuroMonitorBridge:
    """Puente Python ↔ JavaScript para consultas pull y configuración.

    Los métodos públicos son invocados desde el frontend vía ``pywebview.api``.
    Todas las respuestas usan estructuras JSON-serializables (``model_dump(mode="json")``).
    """

    def __init__(
        self,
        app: NeuroMonitorApplication,
        history: HistoryBuffer,
    ) -> None:
        self._app = app
        self._history = history

    def get_current_snapshot(self) -> dict[str, Any]:
        """Última muestra conocida; si el historial está vacío, captura una en caliente."""
        samples = self._history.get_all()
        if samples:
            snapshot = samples[-1]
        else:
            snapshot = self._app.capture_snapshot()
        return self._snapshot_to_dict(snapshot)

    def get_history(self, limit: int = 300) -> list[dict[str, Any]]:
        """Historial reciente acotado por ``limit`` (más recientes al final)."""
        if limit < 1:
            return []

        limit = min(limit, _MAX_HISTORY_LIMIT)

        samples = self._history.get_all()
        window = samples[-limit:] if limit < len(samples) else samples
        return [self._snapshot_to_dict(item) for item in window]

    def update_settings(self, settings_dict: dict[str, Any]) -> dict[str, Any]:
        """Aplica cambios de configuración en caliente (intervalo de refresco, GPU, etc.)."""
        if not isinstance(settings_dict, dict):
            return self._error_response(_ERR_INVALID_SETTINGS, _MSG_INVALID_SETTINGS)

        if set(settings_dict) - _SETTINGS_ALLOWLIST:
            return self._error_response(_ERR_INVALID_SETTINGS, _MSG_INVALID_SETTINGS)

        try:
            merged = self._app._settings.model_dump()
            merged.update(settings_dict)
            validated = Settings.model_validate(merged, strict=True)
            self._apply_settings(validated)

            logger.info(
                "Configuración actualizada: poll_interval_ms=%s enable_gpu=%s",
                validated.poll_interval_ms,
                validated.enable_gpu,
            )
            return {
                "success": True,
                "settings": validated.model_dump(mode="json"),
            }
        except (ValidationError, TypeError, ValueError):
            logger.warning(
                "Error validando configuración desde el frontend",
                exc_info=True,
            )
            return self._error_response(_ERR_INVALID_SETTINGS, _MSG_INVALID_SETTINGS)
        except Exception:
            logger.exception("Error inesperado al actualizar configuración")
            return self._error_response(_ERR_INTERNAL, _MSG_INTERNAL)

    def _apply_settings(self, settings: Settings) -> None:
        """Propaga valores validados al motor de la aplicación."""
        self._app._settings.poll_interval_ms = settings.poll_interval_ms
        self._app._settings.enable_gpu = settings.enable_gpu
        self._app._settings.app_name = settings.app_name

    @staticmethod
    def _snapshot_to_dict(snapshot: SystemSnapshot) -> dict[str, Any]:
        return snapshot.model_dump(mode="json")

    def _error_response(self, code: str, message: str) -> dict[str, Any]:
        return {"success": False, "code": code, "error": message}
