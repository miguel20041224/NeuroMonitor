"""Arranque opcional del servidor HTTP (FastAPI + uvicorn)."""

from __future__ import annotations

import argparse
import logging
import sys

from neuromonitor.config import Settings, get_settings
from neuromonitor.config.settings import LOCALHOST_BIND

logger = logging.getLogger(__name__)


def _api_enabled(settings: Settings, cli_enable: bool) -> bool:
    return settings.enable_api or cli_enable


def _require_api_token(settings: Settings) -> bool:
    """Fail-closed: token obligatorio cuando la API está habilitada (SEC-001)."""
    token = settings.api_token
    if token is None or not token.strip():
        logger.critical(
            "ERROR CRÍTICO DE SEGURIDAD (SEC-001): la API está habilitada pero "
            "NEUROMONITOR_API_TOKEN no está definido o está vacío. "
            "Define un token no vacío antes de arrancar el servidor."
        )
        return False
    return True


def run_api_server(
    *,
    cli_enable: bool = False,
    host: str | None = None,
    port: int | None = None,
) -> int:
    """Levanta uvicorn solo si la API está habilitada explícitamente."""
    settings = get_settings()
    if not _api_enabled(settings, cli_enable):
        logger.error(
            "API de red deshabilitada por defecto (SEC-001). "
            "Define NEUROMONITOR_ENABLE_API=true o usa --enable-api."
        )
        return 1

    if not _require_api_token(settings):
        return 1

    bind_host = host or settings.host
    bind_port = port if port is not None else settings.port

    try:
        import uvicorn
    except ImportError:
        logger.error(
            "uvicorn no está instalado. Instala dependencias API: "
            "pip install 'neuromonitor[api]'"
        )
        return 1

    logger.info("Iniciando API en http://%s:%s (solo si enable_api=true)", bind_host, bind_port)
    uvicorn.run(
        "neuromonitor.api.app:create_app",
        factory=True,
        host=bind_host,
        port=bind_port,
        log_level="info",
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuromonitor-api",
        description="NeuroMonitor — servidor HTTP opcional (deshabilitado por defecto)",
    )
    parser.add_argument(
        "--enable-api",
        action="store_true",
        help="Habilita el servidor (equivalente a NEUROMONITOR_ENABLE_API=true)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help=f"Host de bind (default: {LOCALHOST_BIND})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Puerto TCP (default: 8765)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Nivel de logging (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return run_api_server(
        cli_enable=args.enable_api,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    raise SystemExit(run())
