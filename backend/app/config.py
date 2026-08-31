from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_MAX_APK_BYTES = 512 * 1024 * 1024


def _default_data_dir() -> Path:
    return Path(os.getenv("ANDROID_EMULATOR_DATA_DIR", "./data"))


def _default_max_apk_bytes() -> int:
    raw = os.getenv("ANDROID_EMULATOR_MAX_APK_BYTES")
    return int(raw) if raw else DEFAULT_MAX_APK_BYTES


@dataclass(slots=True)
class Settings:
    data_dir: Path = field(default_factory=_default_data_dir)
    max_apk_bytes: int = field(default_factory=_default_max_apk_bytes)

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        if self.max_apk_bytes <= 0:
            raise ValueError("max_apk_bytes must be positive")
