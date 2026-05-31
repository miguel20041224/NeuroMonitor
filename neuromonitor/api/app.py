from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from neuromonitor.api.rate_limit import register_rate_limit_exception_handler
from neuromonitor.api.routes import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app() -> FastAPI:
    """API opcional; el producto principal opera en modo desktop-only.

    El servidor HTTP no arranca por defecto (ver ``neuromonitor.api.server``).
    WebSocket ``/ws/metrics`` deshabilitado (SEC-009): ``stream_snapshots`` no existe.
    """
    app = FastAPI(
        title="NeuroMonitor API",
        description="Monitoreo en tiempo real de CPU, GPU, RAM y disco",
        version="0.1.0",
        lifespan=lifespan,
    )
    register_rate_limit_exception_handler(app)
    app.include_router(api_router)
    return app
