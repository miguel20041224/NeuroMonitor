"""Modo escritorio: ventana pywebview con bridge in-process."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
from pathlib import Path

from neuromonitor.application.app import NeuroMonitorApplication
from neuromonitor.bridge.pywebview_bridge import NeuroMonitorBridge
from neuromonitor.config.settings import Settings, get_settings
from neuromonitor.models.snapshot import SystemSnapshot
from neuromonitor.services.history_buffer import HistoryBuffer
from neuromonitor.telemetry.engine import TelemetryEngine

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_UI_PATH = PROJECT_ROOT / "assets" / "index.html"


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _resolve_ui_index() -> Path:
    """Resuelve la ruta al HTML principal en ``assets/index.html``."""
    if DEFAULT_UI_PATH.is_file():
        return DEFAULT_UI_PATH
    raise FileNotFoundError(
        f"No se encontró UI en {DEFAULT_UI_PATH}. "
        "Genera el frontend (npm run build) y colócalo en assets/."
    )


def _snapshot_to_js_payload(snapshot: SystemSnapshot) -> str:
    """Serializa el snapshot como literal JSON embebible en evaluate_js."""
    return json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuromonitor-desktop",
        description="NeuroMonitor — ventana nativa con bridge pywebview in-process",
    )
    parser.add_argument("--width", type=int, default=1280, help="Ancho de ventana")
    parser.add_argument("--height", type=int, default=820, help="Alto de ventana")
    parser.add_argument(
        "--history-size",
        type=int,
        default=300,
        help="Máximo de snapshots en el buffer de historial",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Nivel de logging (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_logging(args.log_level)

    try:
        import webview
    except ImportError:
        logger.error(
            "pywebview no está instalado. Instala con: pip install pywebview"
        )
        return 1

    settings: Settings = get_settings()
    history_buffer = HistoryBuffer(max_size=args.history_size)
    app_engine = NeuroMonitorApplication(settings=settings)
    telemetry_engine = TelemetryEngine(run_discovery=True)
    bridge = NeuroMonitorBridge(app_engine, history_buffer, telemetry=telemetry_engine)

    metrics_hub = app_engine.hub

    def persist_snapshot(snapshot: SystemSnapshot) -> None:
        history_buffer.append(snapshot)

    metrics_hub.subscribe(persist_snapshot)

    def stream_to_ui(snapshot: SystemSnapshot) -> None:
        """Push en tiempo real hacia el runtime JS de la ventana (patrón pub/sub)."""
        if not webview.windows:
            return
        payload = _snapshot_to_js_payload(snapshot)
        js = f"if (window.onNewSnapshot) {{ window.onNewSnapshot({payload}); }}"
        try:
            webview.windows[0].evaluate_js(js)
        except Exception:
            logger.debug("evaluate_js omitido (ventana aún no lista o cerrándose)", exc_info=True)

    metrics_hub.subscribe(stream_to_ui)

    metrics_thread = threading.Thread(
        target=app_engine.start,
        name="neuromonitor-app-start",
        daemon=True,
    )
    metrics_thread.start()

    ui_index = _resolve_ui_index()
    ui_url = ui_index.as_uri()

    window = webview.create_window(
        title=settings.app_name,
        url=ui_url,
        width=args.width,
        height=args.height,
        min_size=(960, 640),
        background_color="#000000",
        text_select=True,
        js_api=bridge,
    )

    def on_window_closing() -> bool:
        logger.info("Cerrando ventana; deteniendo motor de métricas…")
        app_engine.stop()
        return True

    window.events.closing += on_window_closing

    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(run())
