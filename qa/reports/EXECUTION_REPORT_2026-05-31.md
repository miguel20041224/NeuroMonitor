# NeuroMonitor — Reporte de ejecución QA (análisis estático + diseño de labs)

**Fecha:** 2026-05-31  
**Versión auditada:** 0.2.0  
**Modo principal:** Escritorio (pywebview + bridge in-process)  
**API FastAPI:** Presente pero con regresiones arquitectónicas detectadas  
**Ejecutor:** QA Senior — revisión estática + laboratorios creados (`qa/labs/`)

---

## 1. Resumen ejecutivo

NeuroMonitor v0.2.0 migró el flujo principal a **aplicación de escritorio** con polling en hilo dedicado y bridge RPC. La arquitectura por capas (collectors → service → application → UI) es coherente y la degradación GPU está bien diseñada (AMD sysfs → NVML → fallback).

**Hallazgos críticos nuevos (v0.2.0):**

| ID | Hallazgo | Severidad |
|----|----------|-----------|
| **BUG-API-001** | `create_app()` referencia `settings.cors_origins` inexistente en `Settings` → **API no arranca** | 🔴 Alto |
| **BUG-API-002** | `websocket/stream.py` llama `MonitorService.stream_snapshots()` **no implementado** → WS roto | 🔴 Alto |
| **BUG-BR-001** | `update_settings({enable_gpu: false})` no propaga al `GpuCollector` existente | 🟡 Medio |
| **BUG-CPU-001** | Dos ventanas `cpu_percent` distintas → global vs per-core desincronizados | 🔴 Alto |
| **BUG-DISK-001** | I/O BPS puede ser negativo tras reset de contadores | 🟡 Medio |

**Estado general:** El **modo escritorio** es viable para demo interna. La **capa API** está en estado **no desplegable** sin correcciones P0.

---

## 2. Casos de prueba ejecutados / diseñados

### 2.1 Laboratorios automatizados (`qa/labs/`)

| Lab | Objetivo | Tests clave | Resultado esperado al ejecutar |
|-----|----------|-------------|--------------------------------|
| LAB_01 | Smoke snapshot | TC-020, TC-091, TC-042 | PASS en hardware normal |
| LAB_02 | Mocks corruptos | TC-023, TC-063 | **FAIL** TC-023 (ValidationError), **FAIL/WARN** TC-063 (BPS negativo) |
| LAB_03 | API contrato | TC-001, TC-010, TC-030 | **FAIL/BLOCKED** cors + stream_snapshots |
| LAB_04 | CPU semántica | TC-041 | **WARN/FAIL** delta > 5% |
| LAB_05 | GPU degradación | TC-070, TC-071 | PASS |
| LAB_06 | Bridge + history | TC-BR-*, TC-004 | **WARN** TC-BR-005 enable_gpu |
| LAB_07 | Desktop polling | TC-DT-* | PASS |
| LAB_08 | Contrato TS | TC-090, F4.3 | PASS schema; WARN semántica I/O |

**Ejecutar batería completa:**

```bash
chmod +x qa/labs/run_all.sh
./qa/labs/run_all.sh
```

### 2.2 Casos manuales

Ver [MANUAL_E2E.md](./MANUAL_E2E.md) y [TEST_CASES.md](./TEST_CASES.md) secciones 1–10.

---

## 3. Escenarios de fallo confirmados

### 🔴 Alto impacto

1. **Snapshot completo cae por ValidationError** (TC-023)  
   - Trigger: `cpu_percent > 100` o NaN desde psutil  
   - Blast radius: REST 500 / poll loop log exception / UI sin datos  

2. **API inoperable** (BUG-API-001 + BUG-API-002)  
   - `create_app()` → AttributeError  
   - WS nunca funcionará sin `stream_snapshots()`  

3. **CPU global ≠ per-core** (F4.1)  
   - UI muestra gauge global inconsistente con barras por núcleo  

### 🟡 Medio impacto

4. **I/O disco negativo** tras suspend/resume o overflow (F2.5)  
5. **Particiones omitidas** sin contador (F2.6) — subestimación de disco  
6. **enable_gpu hot-reload** no efectivo (BUG-BR-001)  
7. **Multi-GPU**: frontend solo grafica `devices[0]`  

### 🟢 Mitigado

8. Sin GPU → fallback degradado con mensaje (F2.1) ✅  
9. Poll loop sobrevive excepciones en capture (LAB_07) ✅  
10. HistoryBuffer rechaza max_size=0 ✅  

---

## 4. Registro de riesgos (actualizado)

| ID | Riesgo | Sev. | Estado |
|----|--------|------|--------|
| R-001 | Fallo en cascada ValidationError | **Alto** | Abierto — LAB_02 confirma |
| R-002 | N× polling WS | **Alto** | 🚫 Bloqueado — método ausente |
| R-003 | Exposición 0.0.0.0 | **Alto** | N/A v0.2 desktop-first (API no default) |
| R-004 | CPU ventanas distintas | **Alto** | Abierto — LAB_04 |
| R-005 | I/O BPS negativo | **Medio** | Abierto — LAB_02 |
| R-021 | **API cors_origins rota** | **Alto** | **Nuevo** |
| R-022 | **stream_snapshots ausente** | **Alto** | **Nuevo** |
| R-023 | **enable_gpu no hot-reload** | **Medio** | **Nuevo** |
| R-014 | Cero tests pytest en repo | **Medio** | Parcial — labs QA creados |

---

## 5. Recomendaciones concretas (priorizadas)

### P0 — Antes de usar API o release público

| # | Acción | Criterio de cierre |
|---|--------|-------------------|
| REC-API-001 | Añadir `cors_origins: list[str] = ["*"]` a Settings **o** eliminar CORS hasta definirlo | LAB_03 TC-001 PASS |
| REC-API-002 | Implementar `stream_snapshots()` con broadcaster único | LAB_03 TC-030 PASS |
| REC-002 | try/except por collector + campos error | LAB_02 TC-023 → WARN no FAIL |
| REC-004 | `clamp_percent()` en collectors | Fuzz 101 → 100 |
| REC-003 | Una sola llamada `cpu_percent(interval, percpu=True)` | LAB_04 delta < 5% |

### P1 — Escritorio producción

| # | Acción |
|---|--------|
| REC-BR-001 | Recrear `GpuCollector` cuando cambie `enable_gpu` |
| REC-006 | Guard monotonicidad I/O disco |
| REC-013 | Etiquetar I/O como agregado sistema en UI |
| REC-011 | Migrar labs a pytest en CI |

### P2 — Observabilidad

| # | Acción |
|---|--------|
| REC-007 | `/health/ready` con snapshot ligero |
| REC-009 | Indicador particiones omitidas |
| REC-010 | Log estructurado en WS 1011 |

---

## 6. Arquitectura evaluada

```
main.py --desktop (default)
    └── desktop.py
          ├── NeuroMonitorApplication (poll thread)
          │     └── MonitorService.capture_snapshot()
          │           ├── CpuCollector      [~50ms block]
          │           ├── MemoryCollector
          │           ├── DiskCollector     [delta state]
          │           └── GpuCollector      [AMD → NVML → fallback]
          ├── HistoryBuffer
          ├── MetricsHub → evaluate_js(onNewSnapshot)
          └── NeuroMonitorBridge (js_api)

main.py --cli
    └── cli.py → NeuroMonitorApplication + ConsolePresenter

API (standalone, rota en v0.2.0)
    └── create_app() → FAIL cors_origins
          └── WS stream_snapshots() → AttributeError
```

**Fortalezas:** separación collectors/service; GPU degradación elegante; HistoryBuffer thread-safe; poll loop resilient.  
**Debilidades:** API desincronizada con refactor desktop; sin aislamiento de fallos; semántica métricas ambigua.

---

## 7. Artefactos entregados

| Artefacto | Ubicación |
|-----------|-----------|
| Laboratorios (8) | `qa/labs/LAB_*.py` |
| Runner consolidado | `qa/labs/run_all.sh` |
| Librería reportes | `qa/labs/lib/` |
| Matriz 100% cobertura | `qa/COVERAGE_MATRIX.md` |
| E2E manual | `qa/MANUAL_E2E.md` |
| Casos de prueba | `qa/TEST_CASES.md` |
| Escenarios de fallo | `qa/FAILURE_SCENARIOS.md` |
| Riesgos | `qa/RISK_REGISTER.md` |
| Recomendaciones | `qa/RECOMMENDATIONS.md` |
| Reportes por ejecución | `qa/reports/labs/`, `qa/reports/EXECUTION_REPORT_*.md` |

---

## 8. Veredicto QA

| Área | Veredicto |
|------|-----------|
| Modo escritorio (core) | ⚠️ **Aceptable con reservas** — P0 CPU/disk semantics |
| Modo CLI | ✅ **OK** para `--once` |
| API REST/WS | ❌ **No desplegar** |
| Frontend | ⚠️ **OK demo** — WARN multi-GPU e I/O labels |
| Suite automatizada | ✅ **Labs creados** — ejecutar `run_all.sh` |

**Próximo paso obligatorio:** ejecutar `./qa/labs/run_all.sh` en CI/local y adjuntar `EXECUTION_REPORT_*.md` a cada release.
