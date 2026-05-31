# Escenarios de fallo — NeuroMonitor

Simulación de estados inválidos, ataques lógicos y condiciones extremas. Objetivo: romper el sistema antes de producción.

---

## Leyenda

| Símbolo | Significado |
|---------|-------------|
| 🔴 | Fallo actual confirmado por análisis estático |
| 🟡 | Degradación parcial o comportamiento indefinido |
| 🟢 | Mitigado o aceptable |

---

## F1. Carga y rendimiento

### F1.1 — Tormenta de clientes WebSocket

| Campo | Detalle |
|-------|---------|
| **Ataque** | Abrir 50–200 conexiones WS a `/ws/metrics` |
| **Mecanismo** | Cada conexión ejecuta `stream_snapshots()` independiente → 50× llamadas a `capture_snapshot()` |
| **Síntoma** | CPU del proceso monitor rivaliza con la carga monitoreada; latencia WS crece |
| **Estado** | 🔴 |
| **Evidencia** | `websocket/stream.py` L19: `async for snapshot in monitor.stream_snapshots()` por cliente |

### F1.2 — Polling REST agresivo

| Campo | Detalle |
|-------|---------|
| **Ataque** | `ab -n 10000 -c 50 http://host:8765/metrics/snapshot` |
| **Mecanismo** | Cada GET bloquea thread pool ~50 ms (CPU sample) + psutil |
| **Síntoma** | Agotamiento thread pool asyncio; timeouts en WS y REST |
| **Estado** | 🔴 |

### F1.3 — Intervalo mínimo de poll (100 ms)

| Campo | Detalle |
|-------|---------|
| **Condición** | `NEUROMONITOR_POLL_INTERVAL_MS=100` + WS |
| **Mecanismo** | 10 snapshots/s × 50 ms CPU block ≈ 50% de un core solo en muestreo |
| **Estado** | 🟡 |

---

## F2. Sensores inexistentes o corruptos

### F2.1 — Sin GPU / sin pynvml

| Campo | Detalle |
|-------|---------|
| **Condición** | Laptop Intel-only, sin `pip install pynvml` |
| **Comportamiento** | `gpu.available=false`, mensaje descriptivo |
| **Estado** | 🟢 |

### F2.2 — Driver NVIDIA cae en runtime

| Campo | Detalle |
|-------|---------|
| **Simulación** | `rmmod nvidia` o mock `NVMLError` en `collect()` |
| **Comportamiento actual** | Todo bloque GPU → `available=false`; REST/WS continúan |
| **Riesgo** | Próximo `collect()` no reintenta `nvmlInit` |
| **Estado** | 🟡 |

### F2.3 — psutil devuelve percent > 100

| Campo | Detalle |
|-------|---------|
| **Simulación** | Mock `cpu_percent` → 100.01 o glitch kernel |
| **Comportamiento** | `ValidationError` en `CpuMetrics` → **snapshot completo falla** |
| **Estado** | 🔴 |
| **Referencia** | `models/metrics.py` L20: `Field(ge=0, le=100)` |

### F2.4 — Memoria total = 0 (VM corrupta / cgroup edge)

| Campo | Detalle |
|-------|---------|
| **Simulación** | Mock `virtual_memory().total = 0` |
| **Comportamiento** | División por cero en UI si calcula ratios; Pydantic puede aceptar percent=0 con total=0 |
| **Estado** | 🟡 |

### F2.5 — Contadores I/O de disco reseteados

| Campo | Detalle |
|-------|---------|
| **Simulación** | Segunda muestra con `read_bytes < last.read_bytes` (reboot counters, overflow uint64) |
| **Comportamiento** | `read_bytes_per_sec` **negativo** |
| **Estado** | 🔴 |
| **Referencia** | `collectors/disk.py` L42-43 sin guard de monotonicidad |

### F2.6 — Particiones con PermissionError

| Campo | Detalle |
|-------|---------|
| **Condición** | Snapshots en `/run/user/...`, `/boot` sin permiso |
| **Comportamiento** | Particiones omitidas sin aviso → UI subestima uso de disco |
| **Estado** | 🟡 |

---

## F3. Condiciones de carrera y estado

### F3.1 — Montaje/desmontaje durante iteración

| Campo | Detalle |
|-------|---------|
| **Simulación** | `mount`/`umount` en loop mientras `disk_partitions()` itera |
| **Comportamiento** | Posible OSError no capturado fuera del try interno |
| **Estado** | 🟡 |

### F3.2 — Hot-plug GPU post-arranque

| Campo | Detalle |
|-------|---------|
| **Condición** | GPU PCIe añadida tras `GpuCollector.__init__` |
| **Comportamiento** | Dispositivo invisible hasta reinicio del servicio |
| **Estado** | 🟡 |

### F3.3 — Cambio de hostname

| Campo | Detalle |
|-------|---------|
| **Condición** | `hostnamectl set-hostname` en runtime |
| **Comportamiento** | Snapshot sigue reportando hostname cacheado en `MonitorService.__init__` |
| **Estado** | 🟢 (bajo impacto) |

---

## F4. Semántica de métricas incorrecta

### F4.1 — CPU global vs per-core desincronizados

| Campo | Detalle |
|-------|---------|
| **Condición** | Spike de CPU entre las dos llamadas `cpu_percent` |
| **Comportamiento** | Gráfico global y desglose por core muestran ventanas temporales distintas |
| **Estado** | 🔴 |
| **Referencia** | `collectors/cpu.py` L14-27 |

### F4.2 — Primera muestra CPU = 0%

| Campo | Detalle |
|-------|---------|
| **Condición** | Primer snapshot tras arranque |
| **Comportamiento** | `percent=0.0` engañoso para alertas |
| **Estado** | 🟡 |

### F4.3 — I/O disco agregado vs particiones

| Campo | Detalle |
|-------|---------|
| **Condición** | UI correlaciona `read_bytes_per_sec` con partición `/` |
| **Comportamiento** | Métrica es **suma del sistema**, no por mountpoint → interpretación errónea |
| **Estado** | 🔴 (fallo de contrato UI/backend) |

---

## F5. Ataques lógicos / seguridad

### F5.1 — Exposición en red (0.0.0.0)

| Campo | Detalle |
|-------|---------|
| **Ataque** | Escaneo puerto 8765 desde LAN |
| **Impacto** | Reconocimiento: hostname, layout discos, modelo GPU, carga sistema |
| **Estado** | 🔴 |
| **Referencia** | `settings.py` L15, `.env.example` |

### F5.2 — WebSocket sin autenticación

| Campo | Detalle |
|-------|---------|
| **Ataque** | Cualquier origen (si CORS no aplica a WS) o script en red local |
| **Impacto** | Stream indefinido de métricas + consumo de recursos (F1.1) |
| **Estado** | 🔴 |

### F5.3 — Slow consumer WS

| Campo | Detalle |
|-------|---------|
| **Ataque** | Cliente acepta conexión pero no lee frames |
| **Impacto** | Buffer interno crece; memoria del servidor |
| **Estado** | 🟡 |

### F5.4 — Health check falso positivo

| Campo | Detalle |
|-------|---------|
| **Ataque** | Orquestador (K8s) usa `/health` para liveness |
| **Impacto** | Pod "healthy" aunque snapshots fallen sistemáticamente |
| **Estado** | 🟡 |

---

## F6. Shutdown y recursos

### F6.1 — NVML leak

| Campo | Detalle |
|-------|---------|
| **Condición** | Kill -9 al proceso |
| **Comportamiento** | `nvmlShutdown()` no ejecutado |
| **Estado** | 🟡 (proceso muerto; driver limpia, pero reinicios rápidos pueden fallar init) |

### F6.2 — Múltiples workers uvicorn

| Campo | Detalle |
|-------|---------|
| **Condición** | `uvicorn --workers 4` |
| **Comportamiento** | 4× `nvmlInit()`, 4× loops WS posibles, estado `DiskCollector` no compartido entre workers |
| **Estado** | 🟡 |

---

## F8. Bridge pywebview — `update_settings`

### F8.1 — Intervalo de polling nulo, negativo o fuera de rango

| Campo | Detalle |
|-------|---------|
| **Ataque** | `pywebview.api.update_settings({ poll_interval_ms: null })` o `-1`, `0`, `999999` |
| **Mecanismo** | Merge parcial sobre `app._settings.model_dump()` → `Settings.model_validate(merged)` |
| **Comportamiento actual** | ValidationError capturada; **frontend recibe `str(exc)` crudo** (nombres de campo, constraints) |
| **Comportamiento ideal** | Log con `exc_info=True`; respuesta `{ success: false, code: "ERR_INVALID_SETTINGS", error: "..." }` |
| **Estado** | 🔴 |
| **Referencia** | `bridge/pywebview_bridge.py` L75-77 |

### F8.2 — Coerción de tipos laxa (bool/string)

| Campo | Detalle |
|-------|---------|
| **Ataque** | `{ enable_gpu: "false" }` (string desde bug JS o payload manual) |
| **Mecanismo** | Pydantic coerciona string no vacío → `True` |
| **Síntoma** | Usuario cree haber desactivado GPU; collector sigue activo |
| **Estado** | 🔴 |
| **Lab** | TC-BR-012 en LAB_06 |

### F8.3 — Inyección de campos API vía bridge desktop

| Campo | Detalle |
|-------|---------|
| **Ataque** | `{ host: "0.0.0.0", allow_remote: false }` |
| **Mecanismo** | Merge incluye campos de `Settings` no expuestos en UI |
| **Síntoma** | Error de validación filtra mensaje interno sobre `NEUROMONITOR_ALLOW_REMOTE` |
| **Estado** | 🔴 |
| **Lab** | TC-BR-015 |

### F8.4 — Intervalo mínimo válido pero malicioso (100 ms)

| Campo | Detalle |
|-------|---------|
| **Ataque** | `{ poll_interval_ms: 100 }` (límite inferior permitido) |
| **Mecanismo** | `_poll_loop` duerme `poll_interval_ms/1000`; 10 capturas/s |
| **Síntoma** | CPU del monitor sube; UI lag en equipos débiles |
| **Estado** | 🟡 |
| **Referencia** | F1.3, `application/app.py` L82-83 |

---

## F9. Cache TTL ausente y hammer REST

### F9.1 — Sin deduplicación de snapshot (SEC-008)

| Campo | Detalle |
|-------|---------|
| **Ataque** | Script: 50× `GET /metrics/snapshot` en 1 s (curl loop, ab, httpx) |
| **Mecanismo** | `metrics.py` → `monitor.capture_snapshot()` sin cache; cada GET ejecuta CPU+disk+mem+GPU |
| **Síntoma** | `cpu_percent(interval=0.05)` × N; ratio psutil/request ≈ 1.0 |
| **Estado** | 🔴 |
| **Referencia** | TC-QA-100, TC-QA-103, LAB_09 |
| **Lab** | LAB_09 |

### F9.2 — Timestamps siempre nuevos bajo ráfaga

| Campo | Detalle |
|-------|---------|
| **Condición** | Dos GET consecutivos en <10 ms |
| **Comportamiento** | `timestamp` distinto en cada respuesta → no hay reutilización de snapshot |
| **Impacto** | Cliente no puede detectar staleness; carga duplicada invisible |
| **Estado** | 🔴 |
| **Referencia** | TC-QA-101 |

### F9.3 — Singleton `@lru_cache` en `get_monitor_service`

| Campo | Detalle |
|-------|---------|
| **Condición** | Cambio de `NEUROMONITOR_ENABLE_GPU` tras arranque (sin reinicio) |
| **Comportamiento** | Misma instancia `MonitorService`; `GpuCollector` conserva flag inicial |
| **Estado** | 🟡 |
| **Referencia** | TC-QA-102, `api/deps.py` |

### F9.4 — Cache TTL mal alineado con poll (futuro)

| Campo | Detalle |
|-------|---------|
| **Simulación** | TTL=5000 ms pero `poll_interval_ms=100` en UI |
| **Comportamiento ideal** | TTL ≤ poll_interval o documentar desfase |
| **Riesgo** | UI muestra datos más viejos que el intervalo declarado |
| **Estado** | 🟡 (preventivo) |

---

## F7. Valores corruptos / fuzzing lógico

| Entrada simulada | Componente | Resultado esperado ideal | Resultado actual |
|------------------|------------|-------------------------|------------------|
| `cpu_percent = NaN` | CpuCollector | Sanitizar → null o degraded | ValidationError 🔴 |
| `disk_usage.percent = 150` | DiskCollector | Clamp 100 o omitir | ValidationError 🔴 |
| `nvmlDeviceGetCount() = 0` | GpuCollector | `available=true`, devices=[] | OK 🟢 |
| JSON WS malformado (cliente→servidor) | WS | Ignorar (servidor no lee) | OK 🟢 |
| Hostname UTF-8 raro | SystemSnapshot | Serialización JSON válida | Probable OK 🟢 |

---

## Matriz de explosión (blast radius)

```
Collector falla (ValidationError)
        │
        ▼
capture_snapshot() excepción
        │
        ├── REST → HTTP 500
        └── WS   → close 1011 (sin mensaje al cliente)

Collectors OK excepto disco omitido
        │
        ▼
UI muestra disco parcial sin indicador → falsa sensación de seguridad

Hammer GET /metrics/snapshot (sin cache TTL)
        │
        ▼
N × capture_snapshot() → N × cpu_percent(0.05) → auto-DoS (F9.1)
```

---

## Escenarios prioritarios para chaos manual

1. **Chaos-01:** 20 clientes WS + stress-ng CPU 100% → observar latencia y CPU del monitor.
2. **Chaos-02:** Mock psutil percent=101 → verificar que REST no cae.
3. **Chaos-03:** Reiniciar contadores I/O (VM suspend/resume) → verificar BPS no negativo.
4. **Chaos-04:** Bind `0.0.0.0` en red WiFi pública → confirmar exposición de `/metrics/snapshot`.
5. **Chaos-05:** Detener driver NVIDIA con WS activo → verificar recuperación tras reinicio driver.
6. **Chaos-06:** `for i in $(seq 1 50); do curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Token: $TOKEN" http://127.0.0.1:8765/metrics/snapshot & done; wait` → medir CPU del proceso y ratio vs LAB_09.
