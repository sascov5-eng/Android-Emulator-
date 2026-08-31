from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class APKRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    sha256: str
    size_bytes: int
    created_at: datetime
