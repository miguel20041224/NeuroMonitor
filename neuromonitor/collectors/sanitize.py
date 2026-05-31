import math


def clamp_percent(value: float) -> float:
    """Normaliza porcentajes del SO antes de validación Pydantic."""
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(100.0, float(value)))
