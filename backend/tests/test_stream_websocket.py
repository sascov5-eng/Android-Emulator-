from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.main import create_app
from app.runtime.models import RuntimeState, RuntimeStatus
from app.stream.input import KeyEvent, PointerEvent
from app.stream.models import StreamState, StreamStatus


class FakeRuntime:
    def __init__(self, state: RuntimeState = RuntimeState.READY) -> None:
        self.state = state

    def status(self):
        return RuntimeStatus(state=self.state, adb_target="127.0.0.1:5555" if self.state is RuntimeState.READY else None)
    def start(self): return self.status()
    def stop(self): self.state = RuntimeState.STOPPED; return self.status()
    def reset(self): self.state = RuntimeState.READY; return self.status()
    def install(self, apk_id, storage): raise AssertionError("not used")
    def launch(self, apk_id, storage): raise AssertionError("not used")
    def list_apps(self): return []


class FakeStream:
    def __init__(self, state: StreamState = StreamState.LIVE) -> None:
        self.state = state

    def status(self):
        return StreamStatus(
            state=self.state,
            session_id="default",
            whep_url="https://media.test/android/session/whep" if self.state is StreamState.LIVE else None,
            width=720,
            height=1280,
            fps=30,
        )
    def start(self): self.state = StreamState.LIVE; return self.status()
    def stop(self): self.state = StreamState.STOPPED; return self.status()


class FakeInputService:
    def __init__(self) -> None:
        self.events = []

    def handle(self, event) -> None:
        self.events.append(event)


def make_client(
    tmp_path: Path,
    *,
    runtime_state: RuntimeState = RuntimeState.READY,
    stream_state: StreamState = StreamState.LIVE,
) -> tuple[TestClient, FakeInputService]:
    input_service = FakeInputService()
    app = create_app(
        Settings(data_dir=tmp_path / "data"),
        runtime_service=FakeRuntime(runtime_state),
        stream_service=FakeStream(stream_state),
        input_service=input_service,
    )
    return TestClient(app), input_service


@pytest.mark.parametrize(
    ("runtime_state", "stream_state"),
    [
        (RuntimeState.STOPPED, StreamState.LIVE),
        (RuntimeState.READY, StreamState.STOPPED),
        (RuntimeState.READY, StreamState.ERROR),
    ],
)
def test_websocket_rejects_when_session_is_not_interactive(tmp_path, runtime_state, stream_state) -> None:
    client, _ = make_client(tmp_path, runtime_state=runtime_state, stream_state=stream_state)

    with pytest.raises(WebSocketDisconnect) as caught:
        with client.websocket_connect("/v1/stream/input"):
            pass

    assert caught.value.code == 4409


def test_websocket_accepts_pointer_and_key_messages(tmp_path: Path) -> None:
    client, input_service = make_client(tmp_path)

    with client.websocket_connect("/v1/stream/input") as ws:
        ws.send_json({"type": "pointer_down", "x": 0.2, "y": 0.3})
        assert ws.receive_json() == {"ok": True}
        ws.send_json({"type": "pointer_up", "x": 0.2, "y": 0.3})
        assert ws.receive_json() == {"ok": True}
        ws.send_json({"type": "key", "key": "home"})
        assert ws.receive_json() == {"ok": True}

    assert isinstance(input_service.events[0], PointerEvent)
    assert isinstance(input_service.events[2], KeyEvent)
    assert input_service.events[2].key == "home"


def test_websocket_rejects_invalid_schema_without_executing_input(tmp_path: Path) -> None:
    client, input_service = make_client(tmp_path)

    with client.websocket_connect("/v1/stream/input") as ws:
        ws.send_json({"type": "key", "key": "power"})
        response = ws.receive_json()

    assert response == {"ok": False, "code": "INPUT_INVALID", "message": "Input event is invalid"}
    assert input_service.events == []


def test_websocket_rejects_non_object_json(tmp_path: Path) -> None:
    client, input_service = make_client(tmp_path)

    with client.websocket_connect("/v1/stream/input") as ws:
        ws.send_json(["shell", "id"])
        response = ws.receive_json()

    assert response["code"] == "INPUT_INVALID"
    assert input_service.events == []
