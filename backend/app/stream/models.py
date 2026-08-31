from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StreamState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    LIVE = "live"
    ERROR = "error"


class StreamStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: StreamState
    session_id: str = "default"
    whep_url: str | None = None
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: int = Field(gt=0)
    error: str | None = None
