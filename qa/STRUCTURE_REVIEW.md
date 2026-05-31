# Revisión de estructura — NeuroMonitor

**Fecha:** 2026-05-31  
**Versión auditada:** 0.1.0  
**Tipo:** Revisión estática de arquitectura (sin ejecución de tests automatizados)

---

## 1. Mapa de componentes

```
main.py → create_app() → FastAPI
              ├── CORS (settings.cors_origins)
              ├── GET /health
              ├── GET /metrics/snapshot → MonitorService.capture_snapshot()
              └── WS /ws/metrics → MonitorService.stream_snapshots()
                        │
                        └── asyncio.to_thread(capture_snapshot)
                                  ├── CpuCollector.collect()      [~50–100 ms bloqueante]
                                  ├── MemoryCollector.collect()
                                  ├── DiskCollector.collect()       [estado delta I/O]
                                  └── GpuCollector.collect()        [NVML opcional]
```

### Fortalezas

| Aspecto | Evaluación |
|---------|------------|
| Separación collectors / service / API | ✅ Clara; collectors no conocen HTTP |
| Contrato `MetricCollector` | ✅ Extensible para nuevas métricas |
| Modelos Pydantic | ✅ Validación de rangos (%, bytes ≥ 0) |
| GPU opcional | ✅ Degradación con `available=false` + `message` |
| I/O async | ✅ `asyncio.to_thread` evita bloquear el event loop |
| Lifespan shutdown | ✅ `GpuCollector.shutdown()` libera NVML |

### Debilidades estructurales

| ID | Capa | Hallazgo |
|----|------|----------|
| STR-01 | Service | Recolección **secuencial**; CPU bloquea antes de RAM/disco/GPU |
| STR-02 | Service | **Sin aislamiento de fallos** entre collectors |
| STR-03 | API | Cada cliente WS ejecuta su **propio loop** de polling |
| STR-04 | API | `/health` no valida sensores ni estado de GPU/NVML |
| STR-05 | Collectors | Disco: I/O agregado del sistema ≠ desglose por partición |
| STR-06 | Config | `host=0.0.0.0` por defecto expone métricas del host |
| STR-07 | Proyecto | **Cero tests**; no hay carpeta `tests/` ni CI |

---

## 2. Análisis por capa

### 2.1 Config (`settings.py`)

```python
host: str = "0.0.0.0"
poll_interval_ms: int = Field(default=1000, ge=100, le=60_000)
enable_gpu: bool = True
```

- `poll_interval_ms` mínimo **100 ms** permite 10 snapshots/s por cliente WS → combinado con muestra CPU de 50 ms genera presión innecesaria.
- `@lru_cache` en `get_settings()` impide recarga en caliente.
- `cors_origins` como `list[str]` en `.env` requiere JSON válido; valor mal formado puede fallar al arranque o ignorarse según pydantic-settings.

### 2.2 Modelos (`metrics.py`, `snapshot.py`)

**Coherencia interna no validada:**

- `MemoryMetrics`: no se comprueba que `used_bytes ≤ total_bytes` ni coherencia `percent` vs bytes.
- `DiskPartitionMetrics`: `used + free` puede no igualar `total` en algunos FS (reservas).
- `CpuMetrics.percent` vs suma de `per_core`: pueden divergir (diseño psutil, no bug de código, pero **contrato UI ambiguo**).
- Validación estricta `le=100`: si psutil/NVML devuelve valor fuera de rango → **ValidationError** → snapshot entero falla.

**Campo huérfano:**

- `MetricKind` definido pero no usado en rutas ni filtros API.

### 2.3 CpuCollector

```python
per_core_raw = psutil.cpu_percent(interval=self._interval, percpu=True)  # bloquea _interval
percent=float(psutil.cpu_percent(interval=None))  # instantáneo, ventana distinta
```

| Problema | Impacto |
|----------|---------|
| Doble llamada con ventanas temporales distintas | Percent global y per-core **no comparables** en la misma muestra |
| Primera llamada `interval=None` | Retorna **0.0** hasta segunda muestra (documentado en psutil, no manejado) |
| `logical_cores=0` si `cpu_count()` falla | UI puede dividir por cero |
| `load_avg_1m` solo Linux | OK en Windows (None), pero frontend debe manejar ausencia |

### 2.4 MemoryCollector

- Passthrough directo de psutil; sin sanitización de NaN/inf (raro pero posible en entornos virtualizados corruptos).
- Sin distinción entre `available` y `free` para el consumidor.

### 2.5 DiskCollector

| Problema | Impacto |
|----------|---------|
| Delta I/O sin manejo de **wraparound/reset** de contadores | `read_bytes_per_sec` negativo o enorme |
| Primera muestra | `read_bytes_per_sec=None` (esperado) |
| `PermissionError` en partición | Se omite **silenciosamente** → UI cree que no existe |
| `disk_partitions(all=False)` | Montajes no estándar pueden quedar fuera |
| Bind mounts duplicados | Misma ruta lógica repetida confunde UI |

### 2.6 GpuCollector

| Problema | Impacto |
|----------|---------|
| NVML init **una sola vez** al construir | GPU hot-plug post-arranque invisible |
| `except Exception` en bucle de dispositivos | Un fallo en GPU índice N → **todo** el bloque GPU en error |
| Sin reintento de init tras fallo transitorio de driver | Reinicio manual del proceso necesario |
| `temperature_c` sin límites | Valores absurdos pasan al frontend |
| Multi-worker uvicorn (si se activa) | Múltiples `nvmlInit()` → comportamiento NVML indefinido |

### 2.7 MonitorService

```python
def capture_snapshot(self) -> SystemSnapshot:
    return SystemSnapshot(
        cpu=self._cpu.collect(),
        memory=self._memory.collect(),
        ...
    )
```

- Una excepción en **cualquier** `collect()` → 500 REST / cierre WS 1011.
- `_hostname` fijado en `__init__`; no refleja cambios de hostname en runtime.
- `CpuCollector(sample_interval=0.05)` hardcodeado; no configurable vía settings (drift vs ARCHITECTURE.md que menciona 50–100 ms).

### 2.8 API

**REST `/metrics/snapshot`**

- Cada request dispara recolección completa incluyendo bloqueo CPU.
- Sin cache, deduplicación ni rate limit → vector de DoS lógico.

**WebSocket `/ws/metrics`**

```python
async for snapshot in monitor.stream_snapshots():
    await websocket.send_text(json.dumps(...))
```

- N conexiones = N loops × N snapshots/s × coste CPU.
- Sin ping/pong timeout configurado explícitamente.
- `except Exception: close(1011)` sin logging → diagnóstico imposible.
- Serialización manual JSON vs `response_model` REST → riesgo de divergencia futura.

**CORS**

- `allow_credentials=True` con orígenes explícitos: correcto si el frontend envía cookies; sin auth actualmente es irrelevante pero prepara superficie si se añade auth por cookie.

---

## 3. Alineación con ARCHITECTURE.md

| Documentado | Implementado | Gap |
|-------------|--------------|-----|
| Poll 500–1000 ms recomendado | Default 1000 ms, mín 100 ms | Mínimo demasiado agresivo |
| WebSocket recomendado | ✅ Implementado | Falta backpressure y fan-out único |
| localhost / proxy auth | Default 0.0.0.0 | **Desalineación de seguridad** |
| Extensiones AMD/Intel/historial | No implementado | OK (futuro) |
| `model_dump_json_api()` | Existe pero WS usa `model_dump` directo | Duplicación menor |

---

## 4. Matriz de dependencias externas

| Dependencia | Fallo si ausente/corrupto | Comportamiento actual |
|-------------|---------------------------|------------------------|
| psutil | Crash o ValidationError | Sin fallback |
| pynvml | `gpu.available=false` | ✅ Aceptable |
| NVIDIA driver | Mensaje en `gpu.message` | ✅ Aceptable |
| Kernel /proc, /sys | OSError en collector | Parcial (disco ignora); resto crash |

---

## 5. Conclusión

La **estructura de carpetas y responsabilidades es adecuada** para un MVP de monitoreo. Los problemas críticos son de **comportamiento bajo estrés y fallo parcial**, no de organización de módulos. La prioridad QA no es reorganizar carpetas, sino:

1. Contratos de degradación parcial por collector.
2. Semántica temporal unificada en CPU.
3. Modelo de fan-out único para WebSocket.
4. Superficie de seguridad (bind, auth, límites).
5. Suite de tests con mocks de sensores.
