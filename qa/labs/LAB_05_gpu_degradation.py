#!/usr/bin/env python3
"""
LAB-05 — GPU: degradación, AMD sysfs, NVML opcional.
Cubre: TC-070, TC-071, TC-072, F2.1, F2.2.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa.labs.lib.report import LabReport, TestResult, default_environment, write_lab_report
from neuromonitor.collectors.gpu import GpuCollector, _collect_amd_sysfs


def main() -> int:
    report = LabReport(
        lab_id="LAB_05",
        lab_name="GPU — degradación y backends",
        started_at=datetime.now(timezone.utc).isoformat(),
        environment=default_environment(),
    )

    # TC-071 — disabled
    disabled = GpuCollector(enabled=False).collect()
    report.add(
        TestResult(
            id="TC-071",
            name="GPU deshabilitado en config",
            status="PASS" if not disabled.available else "FAIL",
            risk="alto",
            message=disabled.message or "sin mensaje",
        )
    )

    # Real collect
    gpu = GpuCollector(enabled=True)
    metrics = gpu.collect()
    gpu.shutdown()

    report.add(
        TestResult(
            id="TC-070",
            name="GPU collect no lanza excepción",
            status="PASS",
            risk="alto",
            message=f"available={metrics.available}, devices={len(metrics.devices)}",
            evidence=metrics.message or metrics.devices[0].name if metrics.devices else "none",
        )
    )

    amd = _collect_amd_sysfs()
    report.add(
        TestResult(
            id="TC-070-amd",
            name="Backend AMD sysfs",
            status="PASS" if amd else "WARN",
            risk="medio",
            message="AMD sysfs disponible" if amd else "AMD sysfs no detectado (esperado en Intel/NVIDIA-only)",
        )
    )

    # Degraded fallback structure
    fallback = GpuCollector._degraded_fallback()
    has_placeholder = (
        not fallback.available
        and fallback.devices
        and fallback.message
    )
    report.add(
        TestResult(
            id="TC-072-fallback",
            name="Fallback degradado estructurado",
            status="PASS" if has_placeholder else "FAIL",
            risk="medio",
            message=fallback.message or "",
        )
    )

    report.finish()
    _, md_path = write_lab_report(report, ROOT / "qa" / "reports" / "labs")
    print(f"Reporte: {md_path}")
    print("Resumen:", report.summary)
    return 0 if report.summary.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
