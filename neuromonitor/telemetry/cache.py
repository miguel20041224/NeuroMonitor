"""Liberación de caché del sistema (Linux nativo)."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DROP_CACHES = Path("/proc/sys/vm/drop_caches")


def clear_system_cache() -> dict[str, Any]:
    """Sincroniza buffers y, si es posible, vacía page cache del kernel."""
    try:
        subprocess.run(["sync"], check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("sync falló: %s", exc)
        return {
            "success": False,
            "message": "No se pudo sincronizar buffers del sistema",
            "error": str(exc),
        }

    if not _DROP_CACHES.is_file():
        return {
            "success": True,
            "message": "Buffers sincronizados (drop_caches no disponible en este kernel)",
        }

    try:
        _DROP_CACHES.write_text("3", encoding="ascii")
    except PermissionError:
        return {
            "success": False,
            "message": "Requiere permisos de administrador para vaciar la caché del kernel",
            "error": "permission_denied",
        }
    except OSError as exc:
        logger.debug("drop_caches falló: %s", exc)
        return {
            "success": False,
            "message": "No se pudo vaciar la caché del kernel",
            "error": str(exc),
        }

    return {
        "success": True,
        "message": "Caché del sistema liberada",
    }
