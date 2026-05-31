#!/usr/bin/env python3
"""Elimina por completo el árbol legacy src/ (SEC-025 / SEC-021).

Fuente de verdad única: neuromonitor/ en la raíz del proyecto.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEGACY_SRC = ROOT / "src"


def main() -> int:
    if not LEGACY_SRC.exists():
        print(f"OK: {LEGACY_SRC} ya no existe.")
        return 0
    shutil.rmtree(LEGACY_SRC)
    print(f"Eliminado: {LEGACY_SRC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
