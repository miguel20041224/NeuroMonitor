#!/usr/bin/env bash
# Ejecuta todos los laboratorios QA y genera reporte consolidado.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

REPORT_DIR="$ROOT/qa/reports"
LAB_DIR="$ROOT/qa/labs"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CONSOLIDATED="$REPORT_DIR/EXECUTION_REPORT_${STAMP}.md"
CONSOLIDATED_JSON="$REPORT_DIR/EXECUTION_REPORT_${STAMP}.json"

mkdir -p "$REPORT_DIR/labs"

LABS=(
  LAB_01_smoke_snapshot.py
  LAB_02_collectors_mocks.py
  LAB_03_api_contract.py
  LAB_04_cpu_semantics.py
  LAB_05_gpu_degradation.py
  LAB_06_bridge_history.py
  LAB_07_desktop_polling.py
  LAB_08_frontend_contract.py
  LAB_09_cache_ttl.py
)

PASS=0
FAIL=0
WARN=0
SKIP=0
BLOCKED=0

{
  echo "# NeuroMonitor — Reporte de ejecución QA"
  echo ""
  echo "- **Fecha:** $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- **Versión auditada:** 0.2.0"
  echo "- **Entorno:** $(python3 --version 2>&1) / $(uname -srmo 2>/dev/null || uname -a)"
  echo ""
  echo "## Resultados por laboratorio"
  echo ""
  echo "| Lab | Script | Exit |"
  echo "|-----|--------|------|"
} > "$CONSOLIDATED"

RESULTS_JSON='{"labs":[]}'
for lab in "${LABS[@]}"; do
  script="$LAB_DIR/$lab"
  if [[ ! -f "$script" ]]; then
    echo "| $lab | MISSING | — |" >> "$CONSOLIDATED"
    FAIL=$((FAIL + 1))
    continue
  fi
  set +e
  python3 "$script" 2>&1 | tee "/tmp/neuromonitor_${lab%.py}.log"
  exit_code=$?
  set -e
  if [[ $exit_code -eq 0 ]]; then
    echo "| ${lab%.py} | OK | 0 |" >> "$CONSOLIDATED"
    PASS=$((PASS + 1))
  else
    echo "| ${lab%.py} | FAIL | $exit_code |" >> "$CONSOLIDATED"
    FAIL=$((FAIL + 1))
  fi
done

{
  echo ""
  echo "## Resumen global"
  echo ""
  echo "| Métrica | Valor |"
  echo "|---------|-------|"
  echo "| Labs OK | $PASS |"
  echo "| Labs FAIL | $FAIL |"
  echo ""
  echo "## Reportes individuales"
  echo ""
  echo "Ver \`qa/reports/labs/\` para JSON y Markdown detallados por lab."
  echo ""
  echo "## Documentación QA"
  echo ""
  echo "- [TEST_CASES.md](../TEST_CASES.md)"
  echo "- [FAILURE_SCENARIOS.md](../FAILURE_SCENARIOS.md)"
  echo "- [RISK_REGISTER.md](../RISK_REGISTER.md)"
  echo "- [RECOMMENDATIONS.md](../RECOMMENDATIONS.md)"
  echo "- [COVERAGE_MATRIX.md](../COVERAGE_MATRIX.md)"
} >> "$CONSOLIDATED"

echo "{\"pass\":$PASS,\"fail\":$FAIL,\"timestamp\":\"$STAMP\"}" > "$CONSOLIDATED_JSON"
echo ""
echo "=== Consolidado: $CONSOLIDATED ==="
exit $(( FAIL > 0 ? 1 : 0 ))
