"""Modo consola: presentador CLI y captura de métricas."""

from __future__ import annotations

import argparse
import logging
import sys

from neuromonitor.application import ConsolePresenter, NeuroMonitorApplication
from neuromonitor.config import get_settings


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuromonitor",
        description="NeuroMonitor — monitoreo de escritorio de CPU, RAM, disco y GPU",
    )
    parser.add_argument(
        "--output",
        choices=("summary", "json"),
        default="summary",
        help="Formato de salida en consola (modo headless)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Captura una sola muestra y termina",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Nivel de logging (DEBUG, INFO, WARNING, ERROR)",
    )
    parser.add_argument(
        "--enable-api",
        action="store_true",
        help="Inicia el servidor HTTP (requiere habilitación explícita; ver NEUROMONITOR_ENABLE_API)",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    if args.enable_api:
        from neuromonitor.api.server import run_api_server

        return run_api_server(cli_enable=True)

    settings = get_settings()
    app = NeuroMonitorApplication(settings=settings)
    presenter = ConsolePresenter()

    if args.output == "json":
        callback = presenter.on_snapshot_json
    else:
        callback = presenter.on_snapshot

    unsubscribe = app.subscribe(callback)

    try:
        if args.once:
            callback(app.capture_snapshot())
            return 0

        app.run_forever()
        return 0
    finally:
        unsubscribe()
        app.stop()


if __name__ == "__main__":
    sys.exit(run())
