#!/usr/bin/env python3
"""Punto de entrada unificado: escritorio (pywebview) o consola (CLI)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuromonitor",
        description="NeuroMonitor — monitoreo de CPU, RAM, disco y GPU",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--desktop",
        action="store_true",
        help="Modo escritorio con pywebview (por defecto)",
    )
    mode.add_argument(
        "--cli",
        action="store_true",
        help="Modo consola con ConsolePresenter",
    )
    mode.add_argument(
        "--api",
        action="store_true",
        help="Servidor HTTP FastAPI (requiere NEUROMONITOR_ENABLE_API=true o --enable-api)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    known, rest = parser.parse_known_args(argv)

    if known.api:
        from neuromonitor.api.server import run as run_api

        return run_api(rest)

    if known.cli:
        from neuromonitor.cli import run as run_cli

        return run_cli(rest)

    from neuromonitor.desktop import run as run_desktop

    return run_desktop(rest)


if __name__ == "__main__":
    raise SystemExit(main())
