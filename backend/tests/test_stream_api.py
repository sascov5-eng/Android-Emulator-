from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.runtime.errors import RuntimeNotReady
from app.runtime.models import RuntimeState, RuntimeStatus
from app.stream.errors import StreamStartError, StreamStopError, StreamUnavailable
from app.stream.models import StreamState, StreamStatus


class FakeRuntime:
    def status(self) -> RuntimeStatus:
        return RuntimeStatus(state=RuntimeState.READY, adb_target="127.0.0.1:5555")

    def start(self): return self.status()
    def stop(self): return RuntimeStatus(state=RuntimeState.STOPPED)
    def reset(self): return self.status()
    def install(self, apk_id, storage): raise AssertionError("not used")
    def launch(self, apk_id, storage): raise AssertionError("not used")
    def list_apps(self): return []


class FakeStream:
    def __init__(self) -> None:
        self.error_for: dict[str, Exception] = {}
        self.current = StreamStatus(
            state=StreamState.STOPPED,
            session_id="default",
            width=720,
            height=1280,
            fps=30,
        )

    def _raise(self, op: str) -> None:
        if op in self.error_for:
            raise self.error_for[op]

    def status(self) -> StreamStatus:
        self._raise("status")
        return self.current

    def start(self) -> StreamStatus:
        self._raise("start")
        self.current = StreamStatus(
            state=StreamState.LIVE,
            session_id="default",
            whep_url="https://media.example.test/android/session/whep",
            width=720,
            height=1280,
            fps=30,
        )
        return self.current

    def stop(self) -> StreamStatus:
        self._raise("stop")
        self.current = StreamStatus(
            state=StreamState.STOPPED,
            session_id="default",
            width=720,
            height=1280,
            fps=30,
        )
        return self.current


def make_client(tmp_path: Path) -> tuple[TestClient, FakeStream]:
    settings = Settings(data_dir=tmp_path / "data")
    stream = FakeStream()
    app = create_app(settings, runtime_service=FakeRuntime(), stream_service=stream)
    return TestClient(app), stream


def test_stream_lifecycle_endpoints(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

    assert client.get("/v1/stream/status").json()["state"] == "stopped"
    live = client.post("/v1/stream/start")
    assert live.status_code == 200
    assert live.json()["state"] == "live"
    assert live.json()["whep_url"] == "https://media.example.test/android/session/whep"
    assert client.post("/v1/stream/stop").json()["state"] == "stopped"


@pytest.mark.parametrize(
    ("operation", "method", "path", "error", "status_code", "code"),
    [
        ("start", "post", "/v1/stream/start", RuntimeNotReady("secret runtime"), 409, "RUNTIME_NOT_READY"),
        ("start", "post", "/v1/stream/start", StreamStartError("secret ffmpeg stderr"), 502, "STREAM_START_FAILED"),
        ("start", "post", "/v1/stream/start", StreamUnavailable("secret media detail"), 503, "STREAM_NOT_AVAILABLE"),
        ("status", "get", "/v1/stream/status", StreamUnavailable("secret media detail"), 503, "STREAM_NOT_AVAILABLE"),
        ("stop", "post", "/v1/stream/stop", StreamStopError("secret process detail"), 502, "STREAM_STOP_FAILED"),
    ],
)
def test_stream_errors_are_stable_and_sanitized(
    tmp_path: Path,
    operation: str,
    method: str,
    path: str,
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    client, stream = make_client(tmp_path)
    stream.error_for[operation] = error

    response = getattr(client, method)(path)

    assert response.status_code == status_code
    assert response.json()["code"] == code
    assert "secret" not in response.json()["message"].lower()
