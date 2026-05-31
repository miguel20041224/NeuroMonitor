# Matriz de cobertura QA — NeuroMonitor v0.2.0

Mapa **100% de superficie de aplicación** → casos de prueba → laboratorio → reporte.

## Leyenda

| Símbolo | Significado |
|---------|-------------|
| ✅ | Cubierto por lab automatizado |
| 🔶 | Cubierto por análisis estático / manual |
| ❌ | Sin cobertura |
| 🚫 | Bloqueado por defecto arquitectónico |

---

## Backend — Collectors

| Componente | Archivo | Casos | Lab | Riesgo |
|------------|---------|-------|-----|--------|
| CpuCollector | `collectors/cpu.py` | TC-040, TC-041, TC-042, TC-023 | LAB_01, LAB_02, LAB_04 | Alto |
| MemoryCollector | `collectors/memory.py` | TC-050, TC-051, TC-024 | LAB_01 | Medio |
| DiskCollector | `collectors/disk.py` | TC-060–TC-065 | LAB_01, LAB_02 | Medio |
| GpuCollector | `collectors/gpu.py` | TC-070–TC-074 | LAB_05 | Alto |
| MetricCollector (ABC) | `collectors/base.py` | Contrato extensión | 🔶 STRUCTURE_REVIEW | Bajo |

---

## Backend — Servicios

| Componente | Archivo | Casos | Lab | Riesgo |
|------------|---------|-------|-----|--------|
| MonitorService | `services/monitor_service.py` | TC-020, TC-030 | LAB_01, LAB_03 | Alto |
| HistoryBuffer | `services/history_buffer.py` | TC-HB-001 | LAB_06 | Bajo |

---

## Backend — Aplicación escritorio

| Componente | Archivo | Casos | Lab | Riesgo |
|------------|---------|-------|-----|--------|
| NeuroMonitorApplication | `application/app.py` | TC-DT-001, TC-DT-002 | LAB_07 | Alto |
| MetricsHub | `application/events.py` | Pub/sub concurrente | LAB_07 | Medio |
| ConsolePresenter | `application/console.py` | `--once`, `--output json` | 🔶 manual CLI | Bajo |
| NeuroMonitorBridge | `bridge/pywebview_bridge.py` | TC-BR-001–005, TC-004 | LAB_06 | Medio |
| desktop.py | `desktop.py` | TC-DT-003, evaluate_js | LAB_07, 🔶 manual | Alto |

---

## Backend — API (opcional)

| Componente | Archivo | Casos | Lab | Riesgo |
|------------|---------|-------|-----|--------|
| create_app | `api/app.py` | TC-001, TC-API-001 | LAB_03 | Alto |
| GET /health | `api/routes/health.py` | TC-010, TC-011 | LAB_03 | Medio |
| GET /metrics/snapshot | `api/routes/metrics.py` | TC-020, TC-025, TC-QA-100–103 | LAB_03, LAB_09 | Alto |
| Snapshot cache / TTL | `api/routes/metrics.py` (pendiente) | TC-QA-100, TC-QA-101 | LAB_09 | Alto |
| get_monitor_service singleton | `api/deps.py` | TC-QA-102 | LAB_09 | Medio |
| WS /ws/metrics | `api/websocket/stream.py` | TC-030–TC-034 | LAB_03 🚫 | Alto |

---

## Frontend

| Componente | Archivo | Casos | Lab | Riesgo |
|------------|---------|-------|-----|--------|
| useMetricsBridge | `hooks/useMetricsBridge.tsx` | Demo mode, HISTORY_LIMIT | LAB_08 | Medio |
| Dashboard + Panels | `components/**` | Render con snapshot real | 🔶 MANUAL_E2E | Medio |
| format.ts | `utils/format.ts` | NaN, null, bytes edge | 🔶 LAB_08 parcial | Bajo |
| Tipos snapshot.ts | `types/snapshot.ts` | TC-090 | LAB_08 | Alto |

---

## Cobertura resumida

| Capa | Cubiertos auto | Static/manual | Sin cubrir |
|------|----------------|---------------|------------|
| Collectors | 4/5 | 1/5 | 0 |
| Services | 2/2 | 0 | 0 |
| Application | 3/4 | 1/4 | 0 |
| API | 5/7 | 1/7 | 1 (WS runtime) |
| Frontend | 2/15 | 13/15 | 0 |

**Ejecutar:** `./qa/labs/run_all.sh` + checklist [MANUAL_E2E.md](./MANUAL_E2E.md)
