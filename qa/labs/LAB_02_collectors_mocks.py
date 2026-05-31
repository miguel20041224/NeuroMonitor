#!/usr/bin/env python3
"""
LAB-02 — Collectors con mocks: valores corruptos y resiliencia.
Cubre: CpuCollector, DiskCollector, ValidationError paths.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from qa.labs.lib.mocks import apply_scenario, corrupt_cpu_percent, disk_io_reset, normal_psutil
from qa.labs.lib.report import LabReport, TestResult, default_environment, write_lab_report
from neuromonitor.collectors.cpu import CpuCollector
from neuromonitor.collectors.disk import DiskCollector


def main() -> int:
    report = LabReport(
        lab_id="LAB_02",
        lab_name="Collectors — mocks y valores corruptos",
        started_at=datetime.now(timezone.utc).isoformat(),
        environment=default_environment(),
    )

    # TC-023 — CPU percent > 100
    with apply_scenario(corrupt_cpu_percent()):
        try:
            CpuCollector(sample_interval=0).collect()
            report.add(
                TestResult(
                    id="TC-023",
                    name="CPU percent > 100 no tumba collector",
                    status="FAIL",
                    risk="alto",
                    message="Aceptó 101.5 sin sanitizar — riesgo en producción si psutil glitchea",
                    evidence="models/metrics.py Field(le=100)",
                    recommendation="REC-004: clamp_percent antes de Pydantic",
                )
            )
        except ValidationError as exc:
            report.add(
                TestResult(
                    id="TC-023",
                    name="CPU percent > 100 no tumba collector",
                    status="FAIL",
                    risk="alto",
                    message=f"ValidationError: {exc.errors()[0]['msg']}",
                    evidence="CpuCollector → CpuMetrics",
                    recommendation="REC-002 + REC-004",
                )
            )
        except Exception as exc:
            report.add(
                TestResult(
                    id="TC-023",
                    name="CPU percent > 100 no tumba collector",
                    status="FAIL",
                    risk="alto",
                    message=str(exc),
                )
            )

    # Normal mock
    with apply_scenario(normal_psutil()):
        try:
            cpu = CpuCollector(sample_interval=0).collect()
            report.add(
                TestResult(
                    id="TC-040-mock",
                    name="CPU mock en rango [0,100]",
                    status="PASS" if 0 <= cpu.percent <= 100 else "FAIL",
                    risk="alto",
                    message=f"percent={cpu.percent}",
                )
            )
        except Exception as exc:
            report.add(
                TestResult(
                    id="TC-040-mock",
                    name="CPU mock en rango [0,100]",
                    status="FAIL",
                    risk="alto",
                    message=str(exc),
                )
            )

    # TC-061 / TC-062 / TC-063 — Disk I/O
    with apply_scenario(disk_io_reset()):
        disk = DiskCollector()
        first = disk.collect()
        second = disk.collect()

        report.add(
            TestResult(
                id="TC-061",
                name="Primera muestra I/O = null",
                status="PASS" if first.read_bytes_per_sec is None else "WARN",
                risk="medio",
                message=f"read_bps={first.read_bytes_per_sec}",
            )
        )

        bps = second.read_bytes_per_sec
        negative = bps is not None and bps < 0
        report.add(
            TestResult(
                id="TC-063",
                name="I/O no negativo tras reset contador",
                status="FAIL" if negative else ("PASS" if bps is not None and bps >= 0 else "WARN"),
                risk="medio",
                message=f"read_bps={bps}",
                evidence="collectors/disk.py L42-43",
                recommendation="REC-006: guard de monotonicidad",
            )
        )

    report.finish()
    _, md_path = write_lab_report(report, ROOT / "qa" / "reports" / "labs")
    print(f"Reporte: {md_path}")
    print("Resumen:", report.summary)
    return 0 if report.summary.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
