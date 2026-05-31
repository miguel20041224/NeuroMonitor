from fastapi import APIRouter

from neuromonitor.api.routes.health import router as health_router
from neuromonitor.api.routes.metrics import router as metrics_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
