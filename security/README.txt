================================================================================
  NEUROMONITOR — DOCUMENTACIÓN DE SEGURIDAD
================================================================================

Proyecto   : NeuroMonitor v0.2.0
Auditoría  : 2026-05-31 (revisión completa sobre código actual)
Alcance    : Backend Python (psutil), API FastAPI, bridge pywebview, frontend
Metodología: Revisión estática + STRIDE-lite + simulación ataques lógicos

IMPORTANTE
----------
Estos reportes NO contienen código de producción. Son artefactos de referencia
para el equipo backend al implementar mitigaciones.

ÍNDICE DE REPORTES
------------------
  reports/00_EXECUTIVE_SUMMARY.txt
      Resumen ejecutivo, postura global, top riesgos, mitigaciones recientes.

  reports/01_VULNERABILITIES_REGISTER.txt
      Registro formal SEC-* (ID, riesgo, estado, evidencia, componente).

  reports/02_ATTACK_SCENARIOS.txt
      Escenarios ESC-* simulados desde perspectiva de atacante.

  reports/03_MITIGATION_ROADMAP.txt
      Roadmap P0-P3 con estados HECHO/PARCIAL/PENDIENTE.

  reports/04_FUNCTIONALITY_SECURITY_MAP.txt
      Mapa funcionalidad ↔ datos expuestos ↔ gaps ↔ riesgo.

  reports/05_API_AND_NETWORK_EXPOSURE.txt
      Endpoints, configuración red, CORS, input validation, checklist.

  reports/06_AUDIT_REVISION_LOG.txt
      Changelog entre revisiones; controles nuevos vs pendientes.

  reports/07_SEC-008_RATE_LIMITING_SPEC.txt
      Especificación técnica P1-03: guard 2 req/s, store acotado, HTTP 429 opaco,
      análisis amenazas, blast radius, criterios ACC-008-*.

RELACIÓN CON QA
---------------
Complementa qa/RISK_REGISTER.md, qa/FAILURE_SCENARIOS.md, qa/labs/.
Cruce SEC-* ↔ R-* documentado en 01_VULNERABILITIES_REGISTER.txt.

CONVENCIÓN DE SEVERIDAD
-----------------------
  ALTO  : explotable o impacto grave con probabilidad media/alta
  MEDIO : condiciones adicionales o impacto parcial
  BAJO  : hardening, defensa en profundidad

ESTADO DE REMEDIACIÓN
---------------------
  ABIERTO                  : sin mitigación
  Mitigación en Diseño (P1): especificación aprobada; implementación pendiente
  PARCIAL                  : mitigación incompleta
  MITIGADO                 : control verificable
  ACEPTADO                 : riesgo documentado y aceptado

MITIGACIONES RECIENTES (consultar 06_AUDIT_REVISION_LOG.txt)
------------------------------------------------------------
  - enable_api=false por defecto
  - bind 127.0.0.1 + ALLOW_REMOTE gate
  - WebSocket deshabilitado en paquete neuromonitor/
  - get_history cap 500
  - Códigos error genéricos en collectors y bridge
  - optional-dependencies [api] en pyproject.toml

PRIORIDAD BACKEND INMEDIATA
---------------------------
  1. Eliminar/sincronizar src/neuromonitor/api/ (SEC-025, SEC-021)
  2. NEUROMONITOR_API_TOKEN fail-closed (SEC-001)
  3. Rate limit GET /metrics/snapshot (SEC-008) — spec en 07_SEC-008_RATE_LIMITING_SPEC.txt

MANTENIMIENTO
-------------
Actualizar reportes cuando cambien:
  neuromonitor/api/*
  neuromonitor/bridge/*
  neuromonitor/collectors/*
  neuromonitor/config/settings.py
  neuromonitor/desktop.py
  src/neuromonitor/ (hasta eliminación)

================================================================================
