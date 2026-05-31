# Registro de riesgos — NeuroMonitor

| ID | Riesgo | Sev. | Prob. | Impacto | Estado |
|----|--------|------|-------|---------|--------|
| R-001 | Snapshot completo falla si un collector lanza ValidationError | **Alto** | Media | API 500 / WS cierre | Abierto |
| R-002 | N clientes WS = N loops de polling independientes | **Alto** | Alta | CPU/memoria del monitor | Abierto |
| R-003 | Servicio expuesto en `0.0.0.0` sin auth por defecto | **Alto** | Media | Fuga de topología del sistema | Abierto |
| R-004 | CPU global y per-core de ventanas temporales distintas | **Alto** | Alta | Gráficos engañosos / alertas falsas | Abierto |
| R-005 | I/O disco negativo tras reset de contadores | **Medio** | Media | Gráficos erróneos, alertas falsas | Abierto |
| R-006 | I/O agregado presentado como métrica por partición | **Medio** | Alta | Misinterpretación en UI | Abierto |
| R-007 | Particiones omitidas por permisos sin indicador | **Medio** | Media | Subestimación de uso de disco | Abierto |
| R-008 | `/health` no refleja fallo de sensores | **Medio** | Media | Falsos positivos en orquestación | Abierto |
| R-009 | REST snapshot sin rate limit (DoS lógico) | **Medio** | Media | Denegación de servicio | Abierto |
| R-010 | Primera muestra CPU = 0% | **Medio** | Alta | Alerta falsa post-arranque | Abierto |
| R-011 | NVML sin reinit tras fallo transitorio de driver | **Medio** | Baja | GPU invisible hasta restart | Abierto |
| R-012 | Sin logging en errores WS (1011 silencioso) | **Medio** | Media | Tiempo de diagnóstico alto | Abierto |
| R-013 | `poll_interval_ms` mínimo 100 ms demasiado agresivo | **Medio** | Media | Carga evitable | Abierto |
| R-014 | Cero tests automatizados | **Medio** | Alta | Regresiones no detectadas | Abierto |
| R-015 | Hot-plug GPU no detectado | **Bajo** | Baja | Datos stale | Abierto |
| R-016 | Hostname cacheado en init | **Bajo** | Baja | Etiqueta incorrecta | Abierto |
| R-017 | `MetricKind` no expuesto en API | **Bajo** | N/A | Confusión futura en frontend | Abierto |
| R-018 | Multi-worker uvicorn + NVML indefinido | **Bajo** | Baja | Crash o init fallido | Abierto |
| R-019 | WS slow consumer sin backpressure | **Bajo** | Media | Crecimiento de memoria | Abierto |
| R-020 | Divergencia serialización REST vs WS | **Bajo** | Baja | Bug de contrato futuro | Abierto |
| R-021 | `settings.cors_origins` referenciado pero no definido — API no arranca | **Alto** | Alta | API inutilizable | Abierto |
| R-022 | `MonitorService.stream_snapshots()` ausente — WebSocket roto | **Alto** | Alta | WS inutilizable | Abierto |
| R-023 | `enable_gpu` hot-reload no propaga a GpuCollector | **Medio** | Media | Toggle UI inefectivo | Abierto |
| R-024 | Frontend grafica solo `gpu.devices[0]` | **Medio** | Baja | Multi-GPU invisible | Abierto |
| R-025 | `update_settings` filtra `str(ValidationError)` al frontend | **Alto** | Alta | Info interna / superficie de ataque lógica | Abierto |
| R-026 | Coerción Pydantic: `enable_gpu: "false"` → True | **Alto** | Media | Toggle GPU inefectivo / falsa sensación de control | Abierto |
| R-027 | `poll_interval_ms=100` aplicado en caliente vía bridge | **Medio** | Media | CPU spike del monitor | Abierto |
| R-028 | Sin campo `code` en respuestas de error del bridge | **Medio** | Alta | UI no puede manejar errores de forma estable | Abierto |
| R-029 | Bridge mergea campos API (`host`, `port`) no pensados para UI | **Medio** | Baja | Filtración de mensajes de bind remoto | Abierto |
| R-030 | REST snapshot sin cache TTL ni rate limit (SEC-008) | **Alto** | Alta | Auto-DoS por polling; ratio psutil/request≈1 | Abierto |
| R-031 | `@lru_cache` en `get_monitor_service` — settings stale en API | **Medio** | Media | Toggle GPU/env sin efecto hasta restart | Abierto |

---

## Detalle por riesgo alto

### R-001 — Fallo en cascada del snapshot

**Descripción:** `MonitorService.capture_snapshot()` construye `SystemSnapshot` de forma atómica. Cualquier excepción en un collector propaga al caller.

**Trigger:** psutil devuelve valor fuera de rango Pydantic; OSError no capturado en Memory/CPU.

**Impacto:** Frontend sin datos; monitoreo ciego justo cuando el sistema está bajo estrés.

**Mitigación propuesta:** Wrapper por collector con modelo `CollectorResult[T]` (`ok | degraded | error`).

---

### R-002 — Multiplicación de carga por WebSocket

**Descripción:** Cada conexión WS instancia conceptualmente un productor de snapshots.

**Trigger:** Dashboard con múltiples pestañas, refresh automático, o ataque intencional.

**Impacto:** El monitor consume más recursos que la carga que pretende observar.

**Mitigación propuesta:** Pub/sub interno: un task publica snapshots; WS solo suscribe.

---

### R-003 — Exposición de métricas en red

**Descripción:** Default `NEUROMONITOR_HOST=0.0.0.0` contradice recomendación de ARCHITECTURE.md (localhost).

**Trigger:** Despliegue sin hardening de `.env`.

**Impacto:** Información reconnaissance: discos, GPU, hostname, patrones de carga.

**Mitigación propuesta:** Default `127.0.0.1`; documentar proxy con auth.

---

### R-004 — Semántica CPU inconsistente

**Descripción:** Dos llamadas `cpu_percent` con intervalos diferentes en la misma `collect()`.

**Trigger:** Cualquier carga variable (caso normal).

**Impacto:** UI muestra percent global bajo mientras cores aparecen saturados (o viceversa).

**Mitigación propuesta:** Una sola muestra con `interval=_interval` para global y per-core, o calcular media de per_core como global.

---

## Mapa de calor (Probabilidad × Impacto)

```
Impacto
  Alto │ R-004        R-001
       │ R-006        R-002
       │              R-003
 Medio │ R-007 R-010  R-009
       │ R-008 R-013  R-014
  Bajo │ R-015 R-016  R-019
       └─────────────────────
         Baja   Media   Alta
              Probabilidad
```

---

## Criterios de aceptación para reducir riesgo

| Riesgo | Criterio de cierre |
|--------|-------------------|
| R-001 | Snapshot parcial con HTTP 200 y campo `errors[]` cuando un collector falla |
| R-002 | 10 WS clients: ≤1.2× CPU vs 1 cliente (mismo intervalo) |
| R-003 | Default bind localhost; README advierte explícitamente |
| R-004 | Test automatizado: delta global vs media per_core < 5% en carga estable |
| R-005 | Test: tras reset contador, BPS ≥ 0 o null |

---

## Riesgo residual aceptable (MVP)

- GPU solo NVIDIA (documentado).
- Sin historial persistente.
- `load_avg` solo Linux.
- Omisión de particiones sin permiso **si** se documenta y expone contador `partitions_skipped`.
