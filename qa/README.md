# NeuroMonitor — Reportes QA

Auditoría v0.2.0 (modo escritorio + API legacy). Objetivo: detectar fallos lógicos, edge cases y riesgos **antes** de producción.

## Ejecutar testing

```bash
# Batería completa (9 laboratorios + reporte consolidado)
chmod +x qa/labs/run_all.sh
./qa/labs/run_all.sh

# Laboratorio individual
python3 qa/labs/LAB_01_smoke_snapshot.py
```

Reportes generados en:
- `qa/reports/EXECUTION_REPORT_<timestamp>.md` — consolidado
- `qa/reports/labs/LAB_XX_<timestamp>.json|md` — detalle por lab

## Alcance v0.2.0

| Área | Archivos |
|------|----------|
| Collectors | `neuromonitor/collectors/*.py` |
| Servicios | `services/monitor_service.py`, `history_buffer.py` |
| Escritorio | `application/*`, `bridge/*`, `desktop.py` |
| API | `api/*` (regresiones detectadas) |
| Frontend | `src/neuromonitor/frontend/src/**` |
| Config | `config/settings.py` |

## Documentos

| Documento | Contenido |
|-----------|-----------|
| [EXECUTION_REPORT_2026-05-31.md](./reports/EXECUTION_REPORT_2026-05-31.md) | **Reporte maestro** — hallazgos, veredicto, riesgos |
| [COVERAGE_MATRIX.md](./COVERAGE_MATRIX.md) | Mapa 100% app → tests → labs |
| [TEST_CASES.md](./TEST_CASES.md) | Casos funcionales, negativos y carga |
| [FAILURE_SCENARIOS.md](./FAILURE_SCENARIOS.md) | Escenarios de fallo y chaos |
| [RISK_REGISTER.md](./RISK_REGISTER.md) | Registro de riesgos |
| [RECOMMENDATIONS.md](./RECOMMENDATIONS.md) | Acciones priorizadas |
| [MANUAL_E2E.md](./MANUAL_E2E.md) | Checklist escritorio pywebview |
| [STRUCTURE_REVIEW.md](./STRUCTURE_REVIEW.md) | Revisión arquitectónica |

## Laboratorios

| Lab | Script | Enfoque |
|-----|--------|---------|
| LAB_01 | `LAB_01_smoke_snapshot.py` | Smoke SystemSnapshot |
| LAB_02 | `LAB_02_collectors_mocks.py` | Valores corruptos, I/O |
| LAB_03 | `LAB_03_api_contract.py` | API REST/WS regresiones |
| LAB_04 | `LAB_04_cpu_semantics.py` | Global vs per-core |
| LAB_05 | `LAB_05_gpu_degradation.py` | AMD/NVML/fallback |
| LAB_06 | `LAB_06_bridge_history.py` | Bridge RPC + settings |
| LAB_07 | `LAB_07_desktop_polling.py` | Poll loop + hub |
| LAB_08 | `LAB_08_frontend_contract.py` | TS vs Python |
| LAB_09 | `LAB_09_cache_ttl.py` | Cache TTL, hammer REST, psutil counters |

## Resumen ejecutivo (2026-05-31)

1. **Modo escritorio:** viable con reservas (CPU semantics, I/O negativo).
2. **API FastAPI:** no desplegable — `cors_origins` ausente, `stream_snapshots()` no implementado.
3. **Sin degradación parcial:** un collector roto tumba el snapshot (R-001).
4. **Labs QA creados** — sustituir ausencia de pytest en repo.

## Convenciones de severidad

| Nivel | Criterio |
|-------|----------|
| **Alto** | Pérdida de servicio, datos críticos incorrectos, API rota |
| **Medio** | Degradación parcial, inconsistencias UI, hot-reload roto |
| **Bajo** | Edge case raro, documentación |
