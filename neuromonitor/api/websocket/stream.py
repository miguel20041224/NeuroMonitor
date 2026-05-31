"""WebSocket de métricas — deshabilitado hasta implementar pub/sub (SEC-009).

El endpoint ``/ws/metrics`` llamaba a ``MonitorService.stream_snapshots()``, que no
existe. Eso dejaba conexiones colgadas y un vector de DoS latente. No registrar
este router en ``create_app()`` hasta que exista el stream async documentado.
"""

from fastapi import APIRouter

router = APIRouter()

# SEC-009: endpoint retirado — no descomentar sin stream_snapshots() y límites WS.
#
# @router.websocket("/ws/metrics")
# async def metrics_stream(...) -> None:
#     ...
