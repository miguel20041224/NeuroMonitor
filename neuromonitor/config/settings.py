from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCALHOST_BIND = "127.0.0.1"
_LOCALHOST_BIND = LOCALHOST_BIND


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NEUROMONITOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    poll_interval_ms: int = Field(default=1000, ge=100, le=60_000)
    enable_gpu: bool = True
    app_name: str = "NeuroMonitor"
    enable_api: bool = False
    api_token: str | None = None
    allow_remote: bool = False
    host: str = _LOCALHOST_BIND
    port: int = Field(default=8765, ge=1, le=65535)

    @field_validator("host")
    @classmethod
    def enforce_localhost_bind(cls, value: str, info) -> str:
        normalized = value.strip()
        if normalized in ("0.0.0.0", "::", "[::]"):
            allow_remote = info.data.get("allow_remote", False)
            if not allow_remote:
                raise ValueError(
                    "bind remoto (0.0.0.0) requiere NEUROMONITOR_ALLOW_REMOTE=true"
                )
            return normalized
        if normalized not in (_LOCALHOST_BIND, "localhost"):
            raise ValueError(
                f"host debe ser {_LOCALHOST_BIND} o localhost; recibido: {normalized!r}"
            )
        return _LOCALHOST_BIND


@lru_cache
def get_settings() -> Settings:
    return Settings()
