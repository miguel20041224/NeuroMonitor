#!/usr/bin/env python3
"""
LAB-04 — Semántica CPU: ventana de muestreo global vs per-core.
Cubre: TC-041, F4.1, R-004.
"""

from __future__ import annotations

import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa.labs.lib.report import LabReport, TestResult, default_environment, write_lab_report
from neuromonitor.collectors.cpu import CpuCollector


def main() -> int:
    report = LabReport(
        lab_id="LAB_04",
        lab_name="CPU — semántica global vs per-core",
        started_at=datetime.now(timezone.utc).isoformat(),
        environment=default_environment(),
    )

    collector = CpuCollector(sample_interval=0.05)
    deltas: list[float] = []

    for i in range(5):
        t0 = time.perf_counter()
        cpu = collector.collect()
        elapsed = (time.perf_counter() - t0) * 1000
        if cpu.per_core:
            mean_core = statistics.mean(c.percent for c in cpu.per_core)
            delta = abs(cpu.percent - mean_core)
            deltas.append(delta)
            report.add(
                TestResult(
                    id=f"TC-041-run{i+1}",
                    name=f"Muestra {i+1}: delta global vs media cores",
                    status="PASS" if delta < 15 else "WARN",
                    risk="alto",
                    message=f"global={cpu.percent:.1f}%, media_cores={mean_core:.1f}%, delta={delta:.1f}%",
                    duration_ms=elapsed,
                    evidence="collectors/cpu.py: dos llamadas cpu_percent distintas",
                )
            )
        time.sleep(0.1)

    if deltas:
        avg_delta = statistics.mean(deltas)
        report.add(
            TestResult(
                id="TC-041",
                name="Delta medio global vs per_core (<5% ideal en carga estable)",
                status="PASS" if avg_delta < 5 else ("WARN" if avg_delta < 15 else "FAIL"),
                risk="alto",
                message=f"delta_medio={avg_delta:.2f}%",
                recommendation="REC-003: una sola ventana de muestreo",
            )
        )

    report.finish()
    _, md_path = write_lab_report(report, ROOT / "qa" / "reports" / "labs")
    print(f"Reporte: {md_path}")
    print("Resumen:", report.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
