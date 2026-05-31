from fastapi import APIRouter

from neuromonitor import __version__

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "neuromonitor", "version": __version__}
