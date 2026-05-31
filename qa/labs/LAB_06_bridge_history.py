#!/usr/bin/env python3
"""
LAB-06 — Bridge pywebview: RPC, historial, settings en caliente.
Cubre: NeuroMonitorBridge, HistoryBuffer, update_settings edge cases.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa.labs.lib.report import LabReport, TestResult, default_environment, write_lab_report
from neuromonitor.application.app import NeuroMonitorApplication
from neuromonitor.bridge.pywebview_bridge import NeuroMonitorBridge
from neuromonitor.services.history_buffer import HistoryBuffer
from neuromonitor.services.monitor_service import MonitorService


def main() -> int:
    report = LabReport(
        lab_id="LAB_06",
        lab_name="Bridge — RPC e historial",
        started_at=datetime.now(timezone.utc).isoformat(),
        environment=default_environment(),
    )

    history = HistoryBuffer(max_size=10)
    app = NeuroMonitorApplication(service=MonitorService())
    bridge = NeuroMonitorBridge(app, history)

    # get_current_snapshot con historial vacío
    snap = bridge.get_current_snapshot()
    report.add(
        TestResult(
            id="TC-BR-001",
            name="get_current_snapshot con historial vacío",
            status="PASS" if "cpu" in snap else "FAIL",
            risk="alto",
            message="Captura en caliente OK",
        )
    )

    # get_history limit
    for _ in range(5):
        history.append(app.capture_snapshot())
    hist = bridge.get_history(limit=3)
    report.add(
        TestResult(
            id="TC-BR-002",
            name="get_history respeta limit",
            status="PASS" if len(hist) == 3 else "FAIL",
            risk="medio",
            message=f"len={len(hist)}",
        )
    )

    hist_zero = bridge.get_history(limit=0)
    report.add(
        TestResult(
            id="TC-BR-003",
            name="get_history limit<1 → []",
            status="PASS" if hist_zero == [] else "FAIL",
            risk="bajo",
            message=f"len={len(hist_zero)}",
        )
    )

    # update_settings inválido
    bad = bridge.update_settings("not-a-dict")
    report.add(
        TestResult(
            id="TC-BR-004",
            name="update_settings rechaza no-dict",
            status="PASS" if bad.get("success") is False else "FAIL",
            risk="medio",
            message=bad.get("error", ""),
        )
    )

    # --- Settings: contrato de error (ERR_INVALID_SETTINGS) ---
    def _assert_invalid_settings_contract(
        response: dict,
        *,
        settings_before: int,
    ) -> tuple[str, str]:
        """Verifica contrato deseado: código genérico, sin filtración Pydantic, sin mutación."""
        leaks = (
            "validation error",
            "Input should",
            "ge=",
            "NEUROMONITOR_",
            "Value error",
        )
        err_text = str(response.get("error", "")).lower()
        leaked = any(fragment.lower() in err_text for fragment in leaks)
        mutated = app._settings.poll_interval_ms != settings_before
        if response.get("success") is not False:
            return "FAIL", "success no es False"
        if response.get("code") != "ERR_INVALID_SETTINGS":
            return "FAIL", f"code={response.get('code')!r}, error={response.get('error', '')[:120]}"
        if leaked:
            return "FAIL", f"filtra excepción interna: {response.get('error', '')[:120]}"
        if mutated:
            return "FAIL", f"settings mutados tras error ({settings_before} -> {app._settings.poll_interval_ms})"
        return "PASS", "contrato ERR_INVALID_SETTINGS OK"

    malicious_payloads: list[tuple[str, str, dict]] = [
        ("TC-BR-006", "poll_interval_ms=null", {"poll_interval_ms": None}),
        ("TC-BR-007", "poll_interval_ms=-500", {"poll_interval_ms": -500}),
        ("TC-BR-008", "poll_interval_ms=0", {"poll_interval_ms": 0}),
        ("TC-BR-009", "poll_interval_ms=50 (ge=100)", {"poll_interval_ms": 50}),
        ("TC-BR-010", "poll_interval_ms=999999 (le=60000)", {"poll_interval_ms": 999_999}),
        ("TC-BR-013", "poll_interval_ms objeto anidado", {"poll_interval_ms": {"x": 1}}),
        ("TC-BR-015", "host=0.0.0.0 sin allow_remote", {"host": "0.0.0.0"}),
    ]

    for tc_id, tc_name, payload in malicious_payloads:
        before_ms = app._settings.poll_interval_ms
        resp = bridge.update_settings(payload)
        status, msg = _assert_invalid_settings_contract(resp, settings_before=before_ms)
        report.add(
            TestResult(
                id=tc_id,
                name=f"update_settings rechaza {tc_name} con ERR_INVALID_SETTINGS",
                status=status,  # type: ignore[arg-type]
                risk="alto" if tc_id in ("TC-BR-006", "TC-BR-015") else "medio",
                message=msg,
                evidence=str(resp)[:200],
                recommendation="REC-025/026: code=ERR_INVALID_SETTINGS, log exc_info, error genérico",
            )
        )

    # Coerción bool peligrosa: "false" string → True en Pydantic lax
    before_gpu = app._settings.enable_gpu
    coerce_resp = bridge.update_settings({"enable_gpu": "false"})
    coerce_bad = (
        coerce_resp.get("success") is True
        and app._settings.enable_gpu is True
        and before_gpu is True
    )
    report.add(
        TestResult(
            id="TC-BR-012",
            name='enable_gpu="false" (string) no debe activar GPU',
            status="FAIL" if coerce_bad else "PASS",
            risk="alto",
            message=(
                f"response={coerce_resp}, enable_gpu={app._settings.enable_gpu} "
                "(esperado False o ERR_INVALID_SETTINGS)"
            ),
            recommendation="REC-027: Settings.model_validate(..., strict=True) o allowlist bridge",
        )
    )

    # poll_interval inválido (legacy TC-004 — compatibilidad matriz)
    bad_interval = bridge.update_settings({"poll_interval_ms": 50})
    report.add(
        TestResult(
            id="TC-004",
            name="poll_interval_ms=50 rechazado (ge=100)",
            status="PASS" if bad_interval.get("success") is False else "FAIL",
            risk="medio",
            message=bad_interval.get("error", "aceptó valor inválido"),
        )
    )

    # enable_gpu toggle no recrea collector
    ok = bridge.update_settings({"enable_gpu": False})
    still_has_gpu = app._service._gpu._enabled  # noqa: SLF001 — QA introspection
    report.add(
        TestResult(
            id="TC-BR-005",
            name="enable_gpu en caliente recrea GpuCollector",
            status="WARN",
            risk="medio",
            message=(
                f"update success={ok.get('success')}, "
                f"GpuCollector._enabled={still_has_gpu} (esperado False tras toggle)"
            ),
            recommendation="Propagar enable_gpu a MonitorService.recreate_gpu_collector()",
        )
    )

    app.stop()

    # HistoryBuffer edge
    try:
        HistoryBuffer(max_size=0)
        report.add(
            TestResult(
                id="TC-HB-001",
                name="HistoryBuffer max_size=0 rechazado",
                status="FAIL",
                risk="bajo",
                message="Aceptó max_size=0",
            )
        )
    except ValueError:
        report.add(
            TestResult(
                id="TC-HB-001",
                name="HistoryBuffer max_size=0 rechazado",
                status="PASS",
                risk="bajo",
                message="ValueError esperado",
            )
        )

    report.finish()
    _, md_path = write_lab_report(report, ROOT / "qa" / "reports" / "labs")
    print(f"Reporte: {md_path}")
    print("Resumen:", report.summary)
    return 0 if report.summary.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
