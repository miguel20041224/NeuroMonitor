#!/usr/bin/env python3
"""
LAB-08 — Contrato frontend: tipos TS vs modelos Python.
Análisis estático de alineación (sin npm).
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa.labs.lib.report import LabReport, TestResult, default_environment, write_lab_report
from neuromonitor.models.snapshot import SystemSnapshot


def extract_ts_interface(path: Path, name: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    pattern = rf"export interface {name}\s*\{{([^}}]+)\}}"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return set()
    fields = re.findall(r"^\s*(\w+)\??:", match.group(1), re.MULTILINE)
    return set(fields)


def main() -> int:
    report = LabReport(
        lab_id="LAB_08",
        lab_name="Frontend — contrato TypeScript",
        started_at=datetime.now(timezone.utc).isoformat(),
        environment=default_environment(),
    )

    ts_path = ROOT / "src" / "neuromonitor" / "frontend" / "src" / "types" / "snapshot.ts"
    py_fields = set(SystemSnapshot.model_fields.keys())

    ts_fields = extract_ts_interface(ts_path, "SystemSnapshot")
    missing_in_ts = py_fields - ts_fields
    extra_in_ts = ts_fields - py_fields

    report.add(
        TestResult(
            id="TC-090",
            name="SystemSnapshot TS alineado con Python",
            status="PASS" if not missing_in_ts else "FAIL",
            risk="alto",
            message=f"missing_in_ts={missing_in_ts}, extra_in_ts={extra_in_ts}",
        )
    )

    # F4.3 — I/O agregado vs particiones
    disk_panel = (ROOT / "src" / "neuromonitor" / "frontend" / "src" / "components" / "panels" / "DiskPanel.tsx").read_text(
        encoding="utf-8"
    )
    has_io_label = "Lectura" in disk_panel and "partitions" in disk_panel
    report.add(
        TestResult(
            id="TC-F4.3",
            name="UI documenta I/O como agregado del sistema",
            status="WARN",
            risk="medio",
            message="DiskPanel muestra I/O global junto a particiones sin disclaimer",
            evidence="DiskPanel.tsx: io-stats + partition-list sin separación semántica",
            recommendation="REC-013: etiquetar 'I/O sistema' o desglosar por device",
        )
    )

    # GPU series solo devices[0]
    hook_path = ROOT / "src" / "neuromonitor" / "frontend" / "src" / "hooks" / "useMetricsBridge.tsx"
    hook_text = hook_path.read_text(encoding="utf-8")
    multi_gpu = "devices[0]" in hook_text
    report.add(
        TestResult(
            id="TC-073-ui",
            name="Multi-GPU reflejado en UI",
            status="WARN" if multi_gpu else "PASS",
            risk="medio",
            message="gpuSeriesFrom usa solo devices[0]" if multi_gpu else "OK",
            recommendation="Agregar selector GPU o agregar series",
        )
    )

    report.finish()
    _, md_path = write_lab_report(report, ROOT / "qa" / "reports" / "labs")
    print(f"Reporte: {md_path}")
    print("Resumen:", report.summary)
    return 0 if report.summary.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
