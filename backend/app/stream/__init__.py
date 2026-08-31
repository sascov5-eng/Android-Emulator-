from __future__ import annotations

from ..config import Settings
from .models import StreamState, StreamStatus
from .process import FFmpegScreenrecordAdapter
from .service import StreamManager


def build_stream_service(settings: Settings, runtime: object) -> StreamManager:
    process = FFmpegScreenrecordAdapter(
        adb_bin=settings.adb_bin,
        adb_target=f"{settings.adb_host}:{settings.adb_port}",
        ffmpeg_bin=settings.ffmpeg_bin,
        rtsp_url=settings.stream_rtsp_url,
        width=settings.stream_width,
        height=settings.stream_height,
        fps=settings.stream_fps,
        bitrate=settings.stream_bitrate,
        capture_seconds=settings.stream_capture_seconds,
    )
    return StreamManager(
        runtime=runtime,
        process_adapter=process,
        whep_url=settings.stream_whep_url,
        width=settings.stream_width,
        height=settings.stream_height,
        fps=settings.stream_fps,
        start_timeout_seconds=settings.stream_start_timeout_seconds,
    )


__all__ = [
    "FFmpegScreenrecordAdapter",
    "StreamManager",
    "StreamState",
    "StreamStatus",
    "build_stream_service",
]
