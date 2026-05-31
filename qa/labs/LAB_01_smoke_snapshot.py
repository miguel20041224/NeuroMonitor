#!/usr/bin/env python3
"""
LAB-01 — Smoke: captura de snapshot y contrato SystemSnapshot.
Cubre: MonitorService, collectors reales, modelos Pydantic.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa.labs.lib.report import LabReport, TestResult, default_environment, write_lab_report
from neuromonitor.services.monitor_service import MonitorService


def main() -> int:
    report = LabReport(
        lab_id="LAB_01",
        lab_name="Smoke — Snapshot y contrato",
        started_at=datetime.now(timezone.utc).isoformat(),
        environment=default_environment(),
    )

    # TC-020
    t0 = time.perf_counter()
    try:
        svc = MonitorService()
        snap = svc.capture_snapshot()
        svc.shutdown()
        payload = snap.model_dump(mode="json")
        required = {"timestamp", "hostname", "cpu", "memory", "disk", "gpu"}
        missing = required - set(payload.keys())
        if missing:
            report.add(
                TestResult(
                    id="TC-020",
                    name="Snapshot JSON válido",
                    status="FAIL",
                    risk="alto",
                    message=f"Campos faltantes: {missing}",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )
            )
        else:
            report.add(
                TestResult(
                    id="TC-020",
                    name="Snapshot JSON válido",
                    status="PASS",
                    risk="alto",
                    message="SystemSnapshot serializa todos los campos requeridos",
                    evidence=f"hostname={payload['hostname']}",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )
            )
    except Exception as exc:
        report.add(
            TestResult(
                id="TC-020",
                name="Snapshot JSON válido",
                status="FAIL",
                risk="alto",
                message=str(exc),
                duration_ms=(time.perf_counter() - t0) * 1000,
                recommendation="REC-002: degradación parcial por collector",
            )
        )

    # TC-091
    t0 = time.perf_counter()
    try:
        ts = snap.timestamp.isoformat()
        ok = ts.endswith("+00:00") or ts.endswith("Z")
        report.add(
            TestResult(
                id="TC-091",
                name="Timestamp UTC ISO-8601",
                status="PASS" if ok else "WARN",
                risk="bajo",
                message=ts,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        )
    except NameError:
        report.add(
            TestResult(
                id="TC-091",
                name="Timestamp UTC ISO-8601",
                status="SKIP",
                risk="bajo",
                message="Snapshot no capturado",
            )
        )

    # TC-042 — cores
    t0 = time.perf_counter()
    try:
        cores = len(snap.cpu.per_core)
        logical = snap.cpu.logical_cores
        status = "PASS" if cores == logical else "WARN"
        report.add(
            TestResult(
                id="TC-042",
                name="Coherencia per_core vs logical_cores",
                status=status,
                risk="medio",
                message=f"per_core={cores}, logical_cores={logical}",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        )
    except NameError:
        report.add(
            TestResult(
                id="TC-042",
                name="Coherencia per_core vs logical_cores",
                status="SKIP",
                risk="medio",
                message="Sin snapshot",
            )
        )

    report.finish()
    json_path, md_path = write_lab_report(report, ROOT / "qa" / "reports" / "labs")
    print(f"Reporte: {md_path}")
    print(f"JSON:    {json_path}")
    print("Resumen:", report.summary)
    return 0 if report.summary.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
