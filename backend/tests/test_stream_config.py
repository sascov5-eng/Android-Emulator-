from __future__ import annotations

import pytest

from app.config import Settings


def test_stream_defaults_are_single_session_safe(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)

    assert settings.stream_public_base_url == "http://127.0.0.1:8889"
    assert settings.stream_whep_path == "/android/session/whep"
    assert settings.stream_rtsp_url == "rtsp://127.0.0.1:8554/android/session"
    assert settings.stream_width == 720
    assert settings.stream_height == 1280
    assert settings.stream_fps == 30
    assert settings.stream_capture_seconds == 175


def test_stream_public_base_url_must_be_http(tmp_path) -> None:
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, stream_public_base_url="file:///private/path")


def test_stream_rtsp_ingest_must_be_loopback(tmp_path) -> None:
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, stream_rtsp_url="rtsp://0.0.0.0:8554/android/session")


@pytest.mark.parametrize("capture_seconds", [0, 176])
def test_capture_segment_must_fit_android_screenrecord_limit(tmp_path, capture_seconds: int) -> None:
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, stream_capture_seconds=capture_seconds)


def test_stream_dimensions_fps_and_bitrate_must_be_positive(tmp_path) -> None:
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, stream_width=0)
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, stream_height=0)
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, stream_fps=0)
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, stream_bitrate=0)
