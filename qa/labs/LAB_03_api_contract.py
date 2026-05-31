#!/usr/bin/env python3
"""
LAB-03 — API REST/WebSocket: contrato y regresiones arquitectónicas.
Cubre: FastAPI app, /health, /metrics/snapshot, WS /ws/metrics.
"""

from __future__ import annotations

import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa.labs.lib.report import LabReport, TestResult, default_environment, write_lab_report


def main() -> int:
    report = LabReport(
        lab_id="LAB_03",
        lab_name="API — contrato REST/WS",
        started_at=datetime.now(timezone.utc).isoformat(),
        environment=default_environment(),
    )

    # Verificar Settings vs API
    from neuromonitor.config.settings import Settings

    settings_fields = set(Settings.model_fields.keys())
    if "cors_origins" not in settings_fields:
        report.add(
            TestResult(
                id="TC-API-001",
                name="Settings.cors_origins existe",
                status="FAIL",
                risk="alto",
                message="api/app.py referencia settings.cors_origins pero Settings no lo define",
                evidence="neuromonitor/api/app.py L29",
                recommendation="Añadir cors_origins a Settings o quitar middleware CORS",
            )
        )
    else:
        report.add(
            TestResult(
                id="TC-API-001",
                name="Settings.cors_origins existe",
                status="PASS",
                risk="alto",
                message="Campo presente",
            )
        )

    # stream_snapshots en MonitorService
    from neuromonitor.services.monitor_service import MonitorService

    if not hasattr(MonitorService, "stream_snapshots"):
        report.add(
            TestResult(
                id="TC-030",
                name="MonitorService.stream_snapshots implementado",
                status="BLOCKED",
                risk="alto",
                message="websocket/stream.py llama stream_snapshots() pero MonitorService no lo define",
                evidence="neuromonitor/api/websocket/stream.py L19",
                recommendation="REC-005: implementar broadcaster + stream_snapshots async",
            )
        )
    else:
        sig = inspect.signature(MonitorService.stream_snapshots)
        report.add(
            TestResult(
                id="TC-030",
                name="MonitorService.stream_snapshots implementado",
                status="PASS",
                risk="alto",
                message=f"Firma: {sig}",
            )
        )

    # Intentar crear app FastAPI
    try:
        from neuromonitor.api import create_app

        app = create_app()
        routes = [getattr(r, "path", str(r)) for r in app.routes]
        report.add(
            TestResult(
                id="TC-001",
                name="create_app() arranca sin excepción",
                status="PASS",
                risk="alto",
                message=f"Rutas registradas: {len(routes)}",
            )
        )
    except Exception as exc:
        report.add(
            TestResult(
                id="TC-001",
                name="create_app() arranca sin excepción",
                status="FAIL",
                risk="alto",
                message=str(exc),
                recommendation="Corregir Settings.cors_origins antes de exponer API",
            )
        )
        report.finish()
        _, md_path = write_lab_report(report, ROOT / "qa" / "reports" / "labs")
        print(f"Reporte: {md_path}")
        return 1

    # TestClient si app OK
    try:
        from fastapi.testclient import TestClient

        client = TestClient(app)
        health = client.get("/health")
        report.add(
            TestResult(
                id="TC-010",
                name="GET /health → 200",
                status="PASS" if health.status_code == 200 else "FAIL",
                risk="alto",
                message=f"status={health.status_code}, body={health.json()}",
            )
        )

        snap_resp = client.get("/metrics/snapshot")
        report.add(
            TestResult(
                id="TC-020",
                name="GET /metrics/snapshot → 200",
                status="PASS" if snap_resp.status_code == 200 else "FAIL",
                risk="alto",
                message=f"status={snap_resp.status_code}",
            )
        )
    except ImportError:
        report.add(
            TestResult(
                id="TC-010",
                name="GET /health → 200",
                status="SKIP",
                risk="alto",
                message="fastapi[test] no instalado — pip install httpx",
            )
        )

    report.finish()
    _, md_path = write_lab_report(report, ROOT / "qa" / "reports" / "labs")
    print(f"Reporte: {md_path}")
    print("Resumen:", report.summary)
    fails = report.summary.get("FAIL", 0) + report.summary.get("BLOCKED", 0)
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
