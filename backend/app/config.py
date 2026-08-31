from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_MAX_APK_BYTES = 512 * 1024 * 1024


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _default_data_dir() -> Path:
    return Path(_env("ANDROID_EMULATOR_DATA_DIR", "./data"))


def _default_max_apk_bytes() -> int:
    raw = os.getenv("ANDROID_EMULATOR_MAX_APK_BYTES")
    return int(raw) if raw else DEFAULT_MAX_APK_BYTES


def _default_adb_port() -> int:
    return int(_env("ANDROID_EMULATOR_ADB_PORT", "5555"))


def _default_boot_timeout() -> float:
    return float(_env("ANDROID_EMULATOR_BOOT_TIMEOUT_SECONDS", "120"))


def _env_int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(_env(name, str(default)))


@dataclass(slots=True)
class Settings:
    data_dir: Path = field(default_factory=_default_data_dir)
    max_apk_bytes: int = field(default_factory=_default_max_apk_bytes)

    runtime_driver: str = field(
        default_factory=lambda: _env("ANDROID_EMULATOR_RUNTIME_DRIVER", "docker")
    )
    redroid_image: str = field(
        default_factory=lambda: _env(
            "ANDROID_EMULATOR_REDROID_IMAGE",
            "redroid/redroid:15.0.0-latest",
        )
    )
    runtime_name: str = field(
        default_factory=lambda: _env(
            "ANDROID_EMULATOR_RUNTIME_NAME",
            "android-emulator-redroid",
        )
    )
    runtime_volume: str = field(
        default_factory=lambda: _env(
            "ANDROID_EMULATOR_RUNTIME_VOLUME",
            "android-emulator-data",
        )
    )
    adb_host: str = field(
        default_factory=lambda: _env("ANDROID_EMULATOR_ADB_HOST", "127.0.0.1")
    )
    adb_port: int = field(default_factory=_default_adb_port)
    boot_timeout_seconds: float = field(default_factory=_default_boot_timeout)
    adb_bin: str = field(
        default_factory=lambda: _env("ANDROID_EMULATOR_ADB_BIN", "adb")
    )
    aapt_bin: str = field(
        default_factory=lambda: _env("ANDROID_EMULATOR_AAPT_BIN", "aapt")
    )
    docker_bin: str = field(
        default_factory=lambda: _env("ANDROID_EMULATOR_DOCKER_BIN", "docker")
    )

    stream_public_base_url: str = field(
        default_factory=lambda: _env(
            "ANDROID_EMULATOR_STREAM_PUBLIC_BASE_URL",
            "http://127.0.0.1:8889",
        )
    )
    stream_whep_path: str = field(
        default_factory=lambda: _env(
            "ANDROID_EMULATOR_STREAM_WHEP_PATH",
            "/android/session/whep",
        )
    )
    stream_rtsp_url: str = field(
        default_factory=lambda: _env(
            "ANDROID_EMULATOR_STREAM_RTSP_URL",
            "rtsp://127.0.0.1:8554/android/session",
        )
    )
    stream_width: int = field(
        default_factory=lambda: _env_int("ANDROID_EMULATOR_STREAM_WIDTH", 720)
    )
    stream_height: int = field(
        default_factory=lambda: _env_int("ANDROID_EMULATOR_STREAM_HEIGHT", 1280)
    )
    stream_fps: int = field(
        default_factory=lambda: _env_int("ANDROID_EMULATOR_STREAM_FPS", 30)
    )
    stream_bitrate: int = field(
        default_factory=lambda: _env_int("ANDROID_EMULATOR_STREAM_BITRATE", 4_000_000)
    )
    stream_capture_seconds: int = field(
        default_factory=lambda: _env_int("ANDROID_EMULATOR_STREAM_CAPTURE_SECONDS", 175)
    )
    stream_start_timeout_seconds: float = field(
        default_factory=lambda: _env_float("ANDROID_EMULATOR_STREAM_START_TIMEOUT_SECONDS", 3.0)
    )
    ffmpeg_bin: str = field(
        default_factory=lambda: _env("ANDROID_EMULATOR_FFMPEG_BIN", "ffmpeg")
    )

    @property
    def stream_whep_url(self) -> str:
        return self.stream_public_base_url.rstrip("/") + "/" + self.stream_whep_path.lstrip("/")

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        if self.max_apk_bytes <= 0:
            raise ValueError("max_apk_bytes must be positive")
        if self.runtime_driver != "docker":
            raise ValueError("runtime_driver must be 'docker'")
        if not self.redroid_image.strip():
            raise ValueError("redroid_image must not be empty")
        if not self.runtime_name.strip():
            raise ValueError("runtime_name must not be empty")
        if not self.runtime_volume.strip():
            raise ValueError("runtime_volume must not be empty")
        if self.adb_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("adb_host must be a loopback address")
        if not 1 <= self.adb_port <= 65535:
            raise ValueError("adb_port must be between 1 and 65535")
        if self.boot_timeout_seconds <= 0:
            raise ValueError("boot_timeout_seconds must be positive")
        if not self.adb_bin.strip():
            raise ValueError("adb_bin must not be empty")
        if not self.aapt_bin.strip():
            raise ValueError("aapt_bin must not be empty")
        if not self.docker_bin.strip():
            raise ValueError("docker_bin must not be empty")

        public_url = urlparse(self.stream_public_base_url)
        if public_url.scheme not in {"http", "https"} or not public_url.netloc:
            raise ValueError("stream_public_base_url must be an http(s) URL")
        if not self.stream_whep_path.startswith("/"):
            raise ValueError("stream_whep_path must start with '/'")

        rtsp_url = urlparse(self.stream_rtsp_url)
        if rtsp_url.scheme != "rtsp" or rtsp_url.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("stream_rtsp_url must use loopback RTSP ingest")
        if self.stream_width <= 0 or self.stream_height <= 0:
            raise ValueError("stream dimensions must be positive")
        if self.stream_fps <= 0:
            raise ValueError("stream_fps must be positive")
        if self.stream_bitrate <= 0:
            raise ValueError("stream_bitrate must be positive")
        if not 1 <= self.stream_capture_seconds <= 175:
            raise ValueError("stream_capture_seconds must be between 1 and 175")
        if self.stream_start_timeout_seconds <= 0:
            raise ValueError("stream_start_timeout_seconds must be positive")
        if not self.ffmpeg_bin.strip():
            raise ValueError("ffmpeg_bin must not be empty")
