from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RuntimeState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    STOPPING = "stopping"
    ERROR = "error"


class RuntimeEndpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    adb_host: str
    adb_port: int = Field(ge=1, le=65535)

    @property
    def adb_target(self) -> str:
        return f"{self.adb_host}:{self.adb_port}"


class RuntimeStatus(BaseModel):
    state: RuntimeState
    adb_target: str | None = None
    error: str | None = None


class AndroidApp(BaseModel):
    package_name: str
    activity_name: str | None = None
    label: str | None = None
