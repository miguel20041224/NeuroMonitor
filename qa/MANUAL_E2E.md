# Checklist E2E manual — Modo escritorio

Ejecutar tras `qa/labs/run_all.sh`. No requiere código de producción.

## Precondiciones

- `pip install -e ".[desktop,gpu]"` (GPU opcional)
- Frontend compilado en `assets/` (`npm run build` en `src/neuromonitor/frontend`)
- Display disponible (X11/Wayland)

## Casos

| ID | Acción | Resultado esperado | Riesgo |
|----|--------|-------------------|--------|
| E2E-001 | `python main.py --desktop` | Ventana abre, status `live` en ≤3s | Alto |
| E2E-002 | Observar 60s | Sparklines avanzan; timestamp actualiza | Alto |
| E2E-003 | Cerrar ventana | Proceso termina; sin zombie threads | Medio |
| E2E-004 | `stress-ng --cpu 4 -t 30s` en paralelo | CPU panel ≥80%; app responsive | Alto |
| E2E-005 | DevTools (si debug) | Sin errores JS en consola | Medio |
| E2E-006 | Sin GPU / sin pynvml | Panel GPU muestra degradado | Medio |
| E2E-007 | `python main.py --cli --once --output json` | JSON válido en stdout | Bajo |

## Registro

Anotar resultados en el reporte consolidado del día o en `qa/reports/manual/E2E_<fecha>.md`.
