# NeuroMonitor

Aplicación de **escritorio** en Python para monitoreo en tiempo real de **CPU**, **RAM**, **disco** y **GPU** (NVIDIA vía NVML).

La arquitectura, modelos y flujo hacia la UI están en [ARCHITECTURE.md](./ARCHITECTURE.md).

## Inicio rápido

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
# GPU NVIDIA (opcional):
pip install -r requirements-gpu.txt

cp .env.example .env
python main.py
```

### Opciones CLI

| Flag | Descripción |
|------|-------------|
| `--once` | Una sola muestra y sale |
| `--output summary` | Resumen legible (default) |
| `--output json` | JSON completo por línea |
| `--log-level DEBUG` | Más detalle en logs |
