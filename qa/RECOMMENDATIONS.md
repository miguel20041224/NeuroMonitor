# Recomendaciones — NeuroMonitor

Acciones concretas priorizadas. **No incluyen código de producción**; son especificaciones para el equipo de desarrollo.

---

## Prioridad 0 — Antes de cualquier demo pública

### REC-001 — Cambiar bind por defecto a localhost

| Campo | Valor |
|-------|-------|
| **Qué** | `Settings.host` default `"127.0.0.1"`; `.env.example` alineado |
| **Por qué** | R-003: exposición involuntaria de métricas |
| **Criterio** | Con `.env` vacío, puerto 8765 no accesible desde otra máquina |

### REC-002 — Degradación parcial por collector

| Campo | Valor |
|-------|-------|
| **Qué** | En `capture_snapshot()`, envolver cada `collect()` en try/except; incluir en snapshot campos opcionales `cpu_error`, `memory_error`, etc., o wrapper `Result` |
| **Por qué** | R-001: un sensor roto no debe tumbar todo |
| **Criterio** | Mock de CPU fallando → REST 200 con `cpu` null y mensaje de error |

### REC-003 — Unificar ventana de muestreo CPU

| Campo | Valor |
|-------|-------|
| **Qué** | Una llamada `cpu_percent(interval=..., percpu=True)`; derivar percent global como media de cores o segunda llamada documentada con mismo interval |
| **Por qué** | R-004: datos inconsistentes en UI |
| **Criterio** | TC-041: delta < 5% en carga estable |

### REC-004 — Sanitizar valores antes de Pydantic

| Campo | Valor |
|-------|-------|
| **Qué** | Función `clamp_percent(x) -> float` en capa collector; ignorar NaN/inf |
| **Por qué** | R-001: ValidationError por 100.001 |
| **Criterio** | Fuzz percent 100.5 → snapshot válido con 100.0 |

---

## Prioridad 1 — Antes de release 0.2.0

### REC-005 — Fan-out único para WebSocket

| Campo | Valor |
|-------|-------|
| **Qué** | Task asyncio background que publica snapshots en intervalo; WS handlers suscriben a cola broadcast |
| **Por qué** | R-002: escalabilidad lineal con clientes |
| **Criterio** | 10 clientes WS: CPU monitor ≤ 1.5× vs 1 cliente |

### REC-006 — Guard de monotonicidad en I/O disco

| Campo | Valor |
|-------|-------|
| **Qué** | Si `io.read_bytes < last.read_bytes`, resetear baseline y emitir `null` en ese frame |
| **Por qué** | R-005: BPS negativos |
| **Criterio** | TC-063 pasa |

### REC-007 — Health check profundo

| Campo | Valor |
|-------|-------|
| **Qué** | `GET /health/ready` ejecuta snapshot ligero (memory-only o full con timeout 2s) |
| **Por qué** | R-008: liveness engañoso |
| **Criterio** | psutil mock roto → 503 en `/health/ready`, 200 en `/health` |

### REC-008 — Rate limiting REST

| Campo | Valor |
|-------|-------|
| **Qué** | Middleware: max 10 req/s por IP en `/metrics/snapshot` |
| **Por qué** | R-009: DoS lógico |
| **Criterio** | TC-025: proceso estable bajo 100 req/s |

### REC-029 — Cache TTL de snapshot alineado a poll_interval_ms

| Campo | Valor |
|-------|-------|
| **Qué** | `SnapshotCache` en capa API: reutilizar último `SystemSnapshot` si `now - cached_at < poll_interval_ms` |
| **Por qué** | R-030 / SEC-008: hammer REST no debe multiplicar `cpu_percent(interval=0.05)` |
| **Criterio** | TC-QA-100, TC-QA-101, TC-QA-103 PASS en LAB_09; ratio cpu_calls/request ≤ 0.2 bajo 10 req/s en ventana TTL |

### REC-030 — Evitar singleton eterno en `get_monitor_service`

| Campo | Valor |
|-------|-------|
| **Qué** | Quitar `@lru_cache` o `cache_clear()` en reload de settings / lifespan shutdown |
| **Por qué** | R-031: `enable_gpu` y hostname no se propagan |
| **Criterio** | TC-QA-102 PASS o documentar «reinicio obligatorio» en README API |

### REC-009 — Indicar particiones omitidas

| Campo | Valor |
|-------|-------|
| **Qué** | Campo `disk.skipped_mounts: int` o lista de mountpoints sin permiso |
| **Por qué** | R-007: datos incompletos invisibles |
| **Criterio** | TC-022 detectable en JSON |

### REC-010 — Logging estructurado

| Campo | Valor |
|-------|-------|
| **Qué** | `logging` en collectors (warning) y WS (error con stack en 1011) |
| **Por qué** | R-012: operación ciega |
| **Criterio** | Error simulado aparece en logs con `collector=gpu` |

---

## Prioridad 2 — Mejora continua

### REC-011 — Suite de tests mínima

| Área | Tests sugeridos |
|------|-----------------|
| Collectors | Mock psutil; ValidationError paths |
| Service | Partial failure; hostname |
| API | TestClient snapshot schema; WS 3 frames |
| Contract | Golden JSON `SystemSnapshot` |

Framework: `pytest` + `pytest-asyncio` + `httpx`.

### REC-012 — Configurar sample_interval CPU vía settings

| Campo | Valor |
|-------|-------|
| **Qué** | `NEUROMONITOR_CPU_SAMPLE_MS` default 100 |
| **Por qué** | Alineación ARCHITECTURE.md; tunable en prod |

### REC-013 — Documentar contrato I/O disco

| Campo | Valor |
|-------|-------|
| **Qué** | En ARCHITECTURE.md: `read_bytes_per_sec` es agregado del sistema |
| **Por qué** | R-006: evitar correlación incorrecta en UI |
| **Alternativa** | Per-device counters si psutil/OS lo permiten |

### REC-014 — Límite de conexiones WS

| Campo | Valor |
|-------|-------|
| **Qué** | Max 20 conexiones; 429 o cierre con código custom |
| **Por qué** | R-002, R-019 |

### REC-015 — Reinit GPU tras error NVML

| Campo | Valor |
|-------|-------|
| **Qué** | Tras N fallos consecutivos, `nvmlShutdown()` + `_try_init_nvml()` |
| **Por qué** | R-011 |

### REC-016 — Warm-up CPU explícito

| Campo | Valor |
|-------|-------|
| **Qué** | Primera `collect()` descartada o flag `cpu.warming_up=true` |
| **Por qué** | R-010 |

---

## Recomendaciones de arquitectura (sin cambio de carpetas)

La estructura actual **no requiere reorganización**. Mejoras son comportamentales:

```
Propuesta lógica (mismo repo):

services/
  monitor_service.py      # orquestación
  snapshot_broadcaster.py # NEW: single poll loop + subscribers

models/
  snapshot.py             # + optional errors/degraded flags

collectors/
  *_collector.py          # + sanitize helpers (no new layer)
```

---

## Checklist pre-release QA

- [ ] TC-020, TC-023, TC-030, TC-062, TC-070 ejecutados manualmente
- [ ] Chaos-01 y Chaos-02 completados
- [ ] Default host = 127.0.0.1 verificado
- [ ] OpenAPI `/docs` coincide con payload WS real
- [ ] README advierte riesgo de `0.0.0.0`
- [ ] Sin tests P0 en rojo (cuando existan)

---

## Esfuerzo estimado

| Prioridad | Items | Esfuerzo dev |
|-----------|-------|--------------|
| P0 | REC-001 a REC-004 | 1–2 días |
| P1 | REC-005 a REC-010, REC-029, REC-030 | 3–5 días |
| P2 | REC-011 a REC-016 | 5–8 días |

---

## Prioridad 0 — Bridge desktop (`update_settings`)

### REC-025 — Código de error estable `ERR_INVALID_SETTINGS`

| Campo | Valor |
|-------|-------|
| **Qué** | `_error_response(code, message)` → `{ success, code, error }`; validación → `ERR_INVALID_SETTINGS` |
| **Por qué** | R-025, R-028: frontend no debe parsear excepciones Pydantic |
| **Criterio** | TC-BR-006..010, TC-BR-015 PASS en LAB_06 |

### REC-026 — Log completo interno, respuesta opaca al JS

| Campo | Valor |
|-------|-------|
| **Qué** | `logger.warning(..., exc_info=True)` en ValidationError; payload truncado en log |
| **Por qué** | Diagnóstico sin filtrar stack al frontend |
| **Criterio** | Log contiene traceback; JSON al JS no contiene `"validation error"` |

### REC-027 — Validación estricta del patch de settings

| Campo | Valor |
|-------|-------|
| **Qué** | `model_validate(..., strict=True)` o DTO bridge con solo 3 campos UI |
| **Por qué** | R-026: `"false"` no debe activar GPU |
| **Criterio** | TC-BR-012 PASS |

### REC-028 — Allowlist de claves mutables desde pywebview

| Campo | Valor |
|-------|-------|
| **Qué** | Rechazar claves fuera de `{poll_interval_ms, enable_gpu, app_name}` |
| **Por qué** | R-029: no retarget `host`/`port` desde JS |
| **Criterio** | TC-BR-015 rechazado con código genérico |

---

## Qué NO recomendamos (scope creep)

- Reescribir en otro lenguaje.
- Añadir Redis/Kafka antes de resolver fan-out local.
- Métricas AMD/Intel GPU antes de cerrar riesgos P0 en NVIDIA/psutil.
- Autenticación OAuth completa en MVP; basta token estático en header si se expone en LAN.
