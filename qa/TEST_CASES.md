# Casos de prueba — NeuroMonitor v0.2.0

**Formato:** ID | Precondición | Acción | Resultado esperado | Prioridad | Lab |

---

## 0. Escritorio (flujo principal v0.2)

| ID | Precondición | Acción | Resultado esperado | P | Lab |
|----|--------------|--------|-------------------|---|-----|
| TC-DT-001 | assets/ compilado | `python main.py --desktop` | Ventana abre; status `live` | P0 | LAB_07, E2E |
| TC-DT-002 | App running | Observar 60s | Sparklines avanzan | P0 | E2E |
| TC-DT-003 | Build OK | Verificar assets | `assets/index.html` existe | P0 | LAB_07 |
| TC-BR-001 | Historial vacío | `get_current_snapshot()` | JSON válido capturado en caliente | P0 | LAB_06 |
| TC-BR-005 | GPU enabled | `update_settings({enable_gpu:false})` | GpuCollector deja de reportar GPU | P1 | LAB_06 |
| TC-BR-006 | Bridge activo | `update_settings({poll_interval_ms:null})` | `success=false`, `code=ERR_INVALID_SETTINGS`, settings sin mutar | P0 | LAB_06 |
| TC-BR-007 | Bridge activo | `update_settings({poll_interval_ms:-500})` | Idem F8.1 | P0 | LAB_06 |
| TC-BR-008 | Bridge activo | `update_settings({poll_interval_ms:0})` | Idem F8.1 | P0 | LAB_06 |
| TC-BR-009 | Bridge activo | `update_settings({poll_interval_ms:50})` | Idem F8.1 (ge=100) | P1 | LAB_06 |
| TC-BR-010 | Bridge activo | `update_settings({poll_interval_ms:999999})` | Idem F8.1 (le=60000) | P1 | LAB_06 |
| TC-BR-012 | GPU enabled | `update_settings({enable_gpu:"false"})` | Rechazo o `enable_gpu=false` real (no coerción a True) | P0 | LAB_06 |
| TC-BR-015 | Bridge activo | `update_settings({host:"0.0.0.0"})` | ERR_INVALID_SETTINGS sin filtrar env vars | P1 | LAB_06 |

---

## 1. Smoke / arranque

| ID | Precondición | Acción | Resultado esperado | P | Lab |
|----|--------------|--------|-------------------|---|-----|
| TC-001 | venv + deps API | `create_app()` | App FastAPI sin excepción | P0 | LAB_03 |
| TC-001-cli | venv | `python main.py --cli --once` | Snapshot en consola/JSON | P0 | manual |
| TC-002 | Sin pynvml | Arranque con `NEUROMONITOR_ENABLE_GPU=true` | API up; snapshot con `gpu.available=false` y mensaje claro | P0 |
| TC-003 | `.env` con `POLL_INTERVAL_MS=100` | Arranque | Acepta valor; WS emite ~10 msg/s | P1 |
| TC-004 | `.env` con `POLL_INTERVAL_MS=50` | Arranque | **Rechazo de validación** (ge=100) o error al cargar settings | P1 |
| TC-005 | `NEUROMONITOR_CORS_ORIGINS` JSON inválido | Arranque | Error explícito o fallback documentado | P2 |

---

## 2. REST — `/health`

| ID | Precondición | Acción | Resultado esperado | P |
|----|--------------|--------|-------------------|---|
| TC-010 | Servicio running | `GET /health` | `{"status":"ok","service":"neuromonitor","version":"0.1.0"}` | P0 |
| TC-011 | psutil roto (mock) | `GET /health` | **Actual:** sigue `ok` — **Esperado deseado:** `degraded` o 503 en `/health/ready` | P1 |

---

## 3. REST — `/metrics/snapshot`

| ID | Precondición | Acción | Resultado esperado | P |
|----|--------------|--------|-------------------|---|
| TC-020 | Sistema normal | `GET /metrics/snapshot` | 200; JSON válido contra schema `SystemSnapshot` | P0 |
| TC-021 | Primera petición tras arranque | Snapshot | `cpu.percent` puede ser 0.0 (psutil); documentar para UI | P1 |
| TC-022 | Sin permisos en `/root` mount | Snapshot | Partición omitida; **resto del snapshot intacto** | P1 |
| TC-023 | Mock: `cpu_percent` → 101.5 | Snapshot | **Actual:** 500 ValidationError — **Esperado:** clamp o error parcial CPU | P0 |
| TC-024 | Mock: `virtual_memory().total=0` | Snapshot | Comportamiento definido (percent=0 o degraded), no 500 | P1 |
| TC-025 | 100 req/s concurrentes | Load test REST | Latencia acotada o 429; proceso estable | P0 |

---

## 4. WebSocket — `/ws/metrics`

| ID | Precondición | Acción | Resultado esperado | P |
|----|--------------|--------|-------------------|---|
| TC-030 | Cliente WS | Conectar + recibir 5 frames | JSON válido cada ~`poll_interval_ms` | P0 |
| TC-031 | Cliente cierra socket | Desconectar | Servidor termina loop sin leak; sin traceback | P0 |
| TC-032 | 10 clientes WS simultáneos | Conectar todos | CPU del proceso monitor **no** escala 10× idealmente | P0 |
| TC-033 | Cliente lento (no lee socket) | Backpressure | Buffer acotado o desconexión; no OOM | P1 |
| TC-034 | Mock: `collect()` lanza excepción | WS activo | Cierre 1011; **log** del error | P1 |
| TC-035 | `poll_interval_ms=1000` | Medir timestamps | Jitter < 10% del intervalo bajo carga normal | P2 |

---

## 5. CPU

| ID | Precondición | Acción | Resultado esperado | P |
|----|--------------|--------|-------------------|---|
| TC-040 | Carga CPU ~100% (stress-ng) | Snapshot | `percent` y `per_core` en [0,100]; coherencia documentada | P0 |
| TC-041 | Comparar `percent` vs media de `per_core` | Análisis | Delta explicado o unificada ventana de muestreo | P1 |
| TC-042 | Máquina 1 core | Snapshot | `per_core` length=1; `logical_cores=1` | P2 |
| TC-043 | Hotplug CPU (VM) | Snapshot tras cambio | Sin crash; cores actualizados o flag degraded | P2 |

---

## 6. Memoria

| ID | Precondición | Acción | Resultado esperado | P |
|----|--------------|--------|-------------------|---|
| TC-050 | RAM alta (>95%) | Snapshot | `percent` ≥ 95; bytes coherentes | P0 |
| TC-051 | Swap deshabilitado | Snapshot | `swap_total_bytes=0`; `swap_percent=0` | P1 |
| TC-052 | cgroup limit (contenedor) | Snapshot | `total_bytes` refleja límite cgroup, no RAM física | P1 |

---

## 7. Disco

| ID | Precondición | Acción | Resultado esperado | P |
|----|--------------|--------|-------------------|---|
| TC-060 | Disco >90% lleno | Snapshot | `partitions[].percent` ≥ 90 | P0 |
| TC-061 | Primera muestra tras arranque | Snapshot | `read_bytes_per_sec=null` | P1 |
| TC-062 | Segunda muestra tras 1 s | Snapshot | `read_bytes_per_sec` ≥ 0 finito | P0 |
| TC-063 | Simular reset contador I/O | Snapshot | No valores negativos | P0 |
| TC-064 | Montaje USB durante collect | Snapshot | Sin crash; lista eventualmente consistente | P2 |
| TC-065 | Partición sin permiso | Snapshot | Indicador de particiones omitidas (campo futuro) | P2 |

---

## 8. GPU (NVIDIA)

| ID | Precondición | Acción | Resultado esperado | P |
|----|--------------|--------|-------------------|---|
| TC-070 | GPU NVIDIA + pynvml | Snapshot | `available=true`; ≥1 device con name, util, mem | P0 |
| TC-071 | `NEUROMONITOR_ENABLE_GPU=false` | Snapshot | `available=false`; mensaje configuración | P0 |
| TC-072 | Driver caído mid-run | Snapshot | Degraded GPU; REST/WS siguen | P1 |
| TC-073 | Multi-GPU | Snapshot | Todos los índices presentes | P1 |
| TC-074 | GPU sin sensor temp | Snapshot | `temperature_c=null`; resto OK | P2 |

---

## 9. Configuración y entorno

| ID | Precondición | Acción | Resultado esperado | P |
|----|--------------|--------|-------------------|---|
| TC-080 | `NEUROMONITOR_HOST=127.0.0.1` | Bind | Solo localhost acepta conexiones | P0 |
| TC-081 | Windows / macOS | Snapshot | `load_avg_1m=null`; resto OK | P2 |
| TC-082 | Shutdown SIGTERM | Detener uvicorn | `nvmlShutdown()` invocado (sin leak NVML) | P1 |

---

## 10. Cache TTL y deduplicación (SEC-008 / DoS lógico)

| ID | Precondición | Acción | Resultado esperado | P | Lab |
|----|--------------|--------|-------------------|---|-----|
| TC-QA-100 | API habilitada; `poll_interval_ms=1000` | 10× `GET /metrics/snapshot` en <100 ms | ≤1 `capture_snapshot()` por ventana TTL; psutil no multiplicado | P0 | LAB_09 |
| TC-QA-101 | Cache TTL activo | Comparar `timestamp` en ráfaga | Mismo timestamp o `snapshot_age_ms` ≤ TTL | P1 | LAB_09 |
| TC-QA-102 | `get_monitor_service()` cacheado | Cambiar `enable_gpu` en Settings y nuevo `MonitorService` | Instancia API refleja cambio o documentar reinicio obligatorio | P1 | LAB_09 |
| TC-QA-103 | Mock contador psutil | 10× `capture_snapshot()` rápidos | Reporte `ratio_cpu_calls/request`; FAIL si ratio≈1 sin cache | P0 | LAB_09 |

**Comportamiento actual (v0.2.0):** cada GET llama `capture_snapshot()` directo; sin TTL ni rate limit → TC-QA-100/101 **FAIL** esperado en lab hasta REC-029.

---

## 11. Contrato JSON (regresión schema)

| ID | Precondición | Acción | Resultado esperado | P |
|----|--------------|--------|-------------------|---|
| TC-090 | Snapshot golden | Validar contra JSON Schema / OpenAPI | Todos los campos requeridos presentes | P0 |
| TC-091 | `timestamp` | Verificar | ISO 8601 UTC con sufijo Z | P1 |
| TC-092 | REST vs WS mismo instante | Comparar payloads | Estructura idéntica | P0 |

---

## Prioridades

- **P0:** Bloqueante para release; fallo de servicio o datos críticos incorrectos.
- **P1:** Importante; degradación o inconsistencia significativa.
- **P2:** Edge case o mejora de observabilidad.

## Estado actual de automatización

| Área | Tests existentes |
|------|------------------|
| Labs QA (`qa/labs/`) | ✅ 9 laboratorios + `run_all.sh` |
| pytest en repo | ❌ Pendiente migración |
| Load / chaos | 🔶 Manual (FAILURE_SCENARIOS) |
| E2E escritorio | 🔶 MANUAL_E2E.md |

**Ejecutar:** `./qa/labs/run_all.sh` — reportes en `qa/reports/`.
