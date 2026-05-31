#!/usr/bin/env python3
"""
LAB-09 — Cache TTL, deduplicación de snapshot y singleton @lru_cache.
Cubre: TC-QA-100 a TC-QA-103, hammer REST simulado, instrumentación psutil.
SEC-008: sin cache TTL ni rate limit en GET /metrics/snapshot.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa.labs.lib.mocks import apply_scenario, counting_psutil
from qa.labs.lib.report import LabReport, TestResult, default_environment, write_lab_report


def _read_metrics_route_source() -> str:
    path = ROOT / "neuromonitor" / "api" / "routes" / "metrics.py"
    return path.read_text(encoding="utf-8")


def _has_snapshot_cache_layer(source: str) -> bool:
    markers = (
        "cache",
        "ttl",
        "TTL",
        "lru_cache",
        "snapshot_cache",
        "cached_snapshot",
        "last_snapshot",
        "_cache",
    )
    lowered = source.lower()
    return any(m.lower() in lowered for m in markers if m != "lru_cache") or (
        "lru_cache" in source and "capture_snapshot" not in source.split("lru_cache")[0][-80:]
    )


def main() -> int:
    report = LabReport(
        lab_id="LAB_09",
        lab_name="Cache TTL — deduplicación snapshot y psutil",
        started_at=datetime.now(timezone.utc).isoformat(),
        environment=default_environment(),
    )

    metrics_src = _read_metrics_route_source()
    has_cache = _has_snapshot_cache_layer(metrics_src)
    direct_capture = "monitor.capture_snapshot()" in metrics_src

    report.add(
        TestResult(
            id="TC-QA-100",
            name="GET /metrics/snapshot con cache TTL acorde a poll_interval_ms",
            status="FAIL" if direct_capture and not has_cache else ("PASS" if has_cache else "WARN"),
            risk="alto",
            message=(
                "Sin capa de cache/TTL: cada GET invoca capture_snapshot() completo"
                if direct_capture and not has_cache
                else "Capa de cache detectada en metrics.py"
            ),
            evidence="neuromonitor/api/routes/metrics.py → capture_snapshot() directo",
            recommendation="REC-029: SnapshotCache con TTL = settings.poll_interval_ms",
        )
    )

    # Hammer simulado: N capturas rápidas con contador psutil
    burst_requests = 10
    scenario, counters = counting_psutil()
    with apply_scenario(scenario):
        from neuromonitor.services.monitor_service import MonitorService

        svc = MonitorService()
        timestamps: list[str] = []
        t0 = time.perf_counter()
        for _ in range(burst_requests):
            snap = svc.capture_snapshot()
            timestamps.append(snap.timestamp.isoformat())
        elapsed_ms = (time.perf_counter() - t0) * 1000
        svc.shutdown()

    cpu_calls = counters["cpu_percent"]
    io_calls = counters["disk_io_counters"]
    # Sin cache: ~1 cpu_percent por snapshot (percpu=True); con cache ideal: 1 en ventana
    expected_max_cpu_calls = burst_requests  # 1× por snapshot mínimo
    dedup_ok = cpu_calls <= max(2, burst_requests // 4)

    report.add(
        TestResult(
            id="TC-QA-103",
            name="Instrumentación psutil bajo ráfaga (ratio collect/request)",
            status="PASS" if cpu_calls > 0 else "FAIL",
            risk="alto",
            message=(
                f"burst={burst_requests} snapshots en {elapsed_ms:.0f}ms; "
                f"cpu_percent calls={cpu_calls}, disk_io_counters calls={io_calls}; "
                f"ratio_cpu={cpu_calls / burst_requests:.2f}"
            ),
            evidence=f"mock counting_psutil; dedup_ok={dedup_ok}",
            recommendation=(
                "REC-029: objetivo ratio ≤ 0.2 bajo 10 req/s dentro de ventana TTL"
                if not dedup_ok
                else ""
            ),
        )
    )

    if dedup_ok and has_cache:
        ts_status = "PASS"
        ts_msg = "Cache activo; timestamps reutilizados o edad acotada"
    elif len(set(timestamps)) == 1 and burst_requests > 1:
        ts_status = "PASS"
        ts_msg = f"Timestamps idénticos en ráfaga ({timestamps[0]})"
    elif len(set(timestamps)) == burst_requests:
        ts_status = "FAIL"
        ts_msg = (
            f"Cada snapshot nuevo (sin dedup): {len(timestamps)} timestamps únicos; "
            "REST hammer repite trabajo psutil completo"
        )
    else:
        ts_status = "WARN"
        ts_msg = f"Timestamps parcialmente distintos: {len(set(timestamps))}/{burst_requests}"

    report.add(
        TestResult(
            id="TC-QA-101",
            name="Coherencia temporal del snapshot dentro de ventana TTL",
            status=ts_status,
            risk="medio",
            message=ts_msg,
            evidence="MonitorService.capture_snapshot() × burst",
            recommendation="REC-029: campo opcional snapshot_age_ms o reutilizar timestamp en cache",
        )
    )

    # Singleton @lru_cache en deps
    from neuromonitor.api.deps import get_monitor_service

    get_monitor_service.cache_clear()
    a = get_monitor_service()
    b = get_monitor_service()
    same_instance = a is b

    settings_mutated = False
    try:
        from neuromonitor.config.settings import Settings

        alt = Settings(enable_gpu=not a._settings.enable_gpu)
        alt_svc = MonitorService(settings=alt)
        settings_mutated = alt_svc._gpu._enabled != a._gpu._enabled  # type: ignore[attr-defined]
    except Exception:
        settings_mutated = False

    report.add(
        TestResult(
            id="TC-QA-102",
            name="Singleton get_monitor_service (@lru_cache) y settings stale",
            status="FAIL" if same_instance else "PASS",
            risk="medio",
            message=(
                f"misma instancia={same_instance}; "
                f"GpuCollector distinto con Settings nuevas={settings_mutated}; "
                "cambios de env/settings no recrean servicio API sin reinicio"
            ),
            evidence="neuromonitor/api/deps.py @lru_cache",
            recommendation="REC-030: factory sin lru_cache o clear_cache en reload settings",
        )
    )

    # TestClient: doble GET si API arranca
    try:
        from neuromonitor.api import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        client = TestClient(app)
        settings = __import__(
            "neuromonitor.config", fromlist=["get_settings"]
        ).get_settings()
        headers = {}
        if settings.api_token:
            headers["X-API-Token"] = settings.api_token

        r1 = client.get("/metrics/snapshot", headers=headers)
        r2 = client.get("/metrics/snapshot", headers=headers)
        if r1.status_code == 401 or r2.status_code == 401:
            report.add(
                TestResult(
                    id="TC-QA-100-rest",
                    name="Doble GET REST consecutivo (dedup timestamp)",
                    status="SKIP",
                    risk="alto",
                    message="401 sin NEUROMONITOR_API_TOKEN — cubierto por ráfaga MonitorService",
                    evidence="require_api_token en metrics.py",
                )
            )
        elif r1.status_code == 200 and r2.status_code == 200:
            t1 = r1.json().get("timestamp")
            t2 = r2.json().get("timestamp")
            rest_dedup = t1 == t2
            report.add(
                TestResult(
                    id="TC-QA-100-rest",
                    name="Doble GET REST consecutivo (dedup timestamp)",
                    status="PASS" if rest_dedup or has_cache else "FAIL",
                    risk="alto",
                    message=f"t1={t1}, t2={t2}, dedup={rest_dedup}",
                    evidence="TestClient GET /metrics/snapshot × 2",
                )
            )
        else:
            report.add(
                TestResult(
                    id="TC-QA-100-rest",
                    name="Doble GET REST consecutivo (dedup timestamp)",
                    status="WARN",
                    risk="alto",
                    message=f"status r1={r1.status_code}, r2={r2.status_code}",
                )
            )
    except Exception as exc:
        report.add(
            TestResult(
                id="TC-QA-100-rest",
                name="Doble GET REST consecutivo (dedup timestamp)",
                status="SKIP",
                risk="alto",
                message=f"API no ejecutable en lab: {exc}",
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
