from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from typing import Any

from .errors import StreamStartError, StreamStopError


class FFmpegScreenrecordAdapter:
    def __init__(
        self,
        *,
        adb_bin: str,
        adb_target: str,
        ffmpeg_bin: str,
        rtsp_url: str,
        width: int,
        height: int,
        fps: int,
        bitrate: int,
        capture_seconds: int,
        popen: Callable[..., Any] = subprocess.Popen,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._adb_bin = adb_bin
        self._adb_target = adb_target
        self._ffmpeg_bin = ffmpeg_bin
        self._rtsp_url = rtsp_url
        self._width = width
        self._height = height
        self._fps = fps
        self._bitrate = bitrate
        self._capture_seconds = capture_seconds
        self._popen = popen
        self._sleep = sleep
        self._adb_proc: Any | None = None
        self._ffmpeg_proc: Any | None = None

    def _adb_command(self) -> list[str]:
        return [
            self._adb_bin,
            "-s",
            self._adb_target,
            "exec-out",
            "screenrecord",
            "--output-format=h264",
            "--bit-rate",
            str(self._bitrate),
            "--size",
            f"{self._width}x{self._height}",
            "--time-limit",
            str(self._capture_seconds),
            "-",
        ]

    def _ffmpeg_command(self) -> list[str]:
        return [
            self._ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-f",
            "h264",
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            "copy",
            "-f",
            "rtsp",
            "-rtsp_transport",
            "tcp",
            self._rtsp_url,
        ]

    def start_capture(self) -> None:
        if self.is_alive():
            return
        self.stop_capture(ignore_errors=True)
        try:
            self._adb_proc = self._popen(
                self._adb_command(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
            )
            if self._adb_proc.stdout is None:
                raise StreamStartError("screen capture pipe was not created")
            self._ffmpeg_proc = self._popen(
                self._ffmpeg_command(),
                stdin=self._adb_proc.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                shell=False,
            )
        except StreamStartError:
            self.stop_capture(ignore_errors=True)
            raise
        except Exception as exc:
            self.stop_capture(ignore_errors=True)
            raise StreamStartError("screen capture process failed") from exc

    def is_alive(self) -> bool:
        return (
            self._adb_proc is not None
            and self._ffmpeg_proc is not None
            and self._adb_proc.poll() is None
            and self._ffmpeg_proc.poll() is None
        )

    def wait_until_live(self, timeout_seconds: float) -> bool:
        if not self.is_alive():
            return False
        self._sleep(min(timeout_seconds, 0.1))
        return self.is_alive()

    def stop_capture(self, *, ignore_errors: bool = False) -> None:
        first_error: Exception | None = None
        for proc in (self._ffmpeg_proc, self._adb_proc):
            if proc is None or proc.poll() is not None:
                continue
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception as exc:
                first_error = first_error or exc
                try:
                    proc.kill()
                    proc.wait(timeout=1)
                except Exception:
                    pass
        self._ffmpeg_proc = None
        self._adb_proc = None
        if first_error is not None and not ignore_errors:
            raise StreamStopError("screen capture process failed to stop") from first_error
