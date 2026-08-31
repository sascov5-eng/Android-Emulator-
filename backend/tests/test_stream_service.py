from __future__ import annotations

import pytest

from app.runtime.errors import RuntimeNotReady
from app.runtime.models import RuntimeState, RuntimeStatus
from app.stream import StreamManager, StreamState
from app.stream.errors import StreamStartError


class FakeRuntime:
    def __init__(self, state: RuntimeState = RuntimeState.READY):
        self.current = RuntimeStatus(state=state)

    def status(self) -> RuntimeStatus:
        return self.current


class FakeProcessAdapter:
    def __init__(self, *, live: bool = True, fail_start: bool = False):
        self.live = live
        self.fail_start = fail_start
        self.start_calls = 0
        self.stop_calls = 0

    def start_capture(self) -> None:
        self.start_calls += 1
        if self.fail_start:
            raise StreamStartError("private ffmpeg stderr must not escape")
        self.live = True

    def stop_capture(self) -> None:
        self.stop_calls += 1
        self.live = False

    def is_alive(self) -> bool:
        return self.live

    def wait_until_live(self, timeout_seconds: float) -> bool:
        return self.live


def make_manager(runtime: FakeRuntime, adapter: FakeProcessAdapter) -> StreamManager:
    return StreamManager(
        runtime=runtime,
        process_adapter=adapter,
        whep_url="https://stream.example.test/android/session/whep",
        width=720,
        height=1280,
        fps=30,
        start_timeout_seconds=5,
    )


def test_start_requires_ready_runtime() -> None:
    manager = make_manager(FakeRuntime(RuntimeState.STOPPED), FakeProcessAdapter())

    with pytest.raises(RuntimeNotReady):
        manager.start()


def test_start_transitions_to_live_and_returns_public_metadata() -> None:
    adapter = FakeProcessAdapter(live=False)
    manager = make_manager(FakeRuntime(), adapter)

    status = manager.start()

    assert status.state is StreamState.LIVE
    assert status.session_id == "default"
    assert status.whep_url == "https://stream.example.test/android/session/whep"
    assert (status.width, status.height, status.fps) == (720, 1280, 30)
    assert adapter.start_calls == 1


def test_start_is_idempotent_when_stream_is_live() -> None:
    adapter = FakeProcessAdapter(live=False)
    manager = make_manager(FakeRuntime(), adapter)
    manager.start()

    status = manager.start()

    assert status.state is StreamState.LIVE
    assert adapter.start_calls == 1


def test_status_marks_dead_live_publisher_as_error() -> None:
    adapter = FakeProcessAdapter(live=False)
    manager = make_manager(FakeRuntime(), adapter)
    manager.start()
    adapter.live = False

    status = manager.status()

    assert status.state is StreamState.ERROR
    assert status.whep_url is None


def test_stop_is_idempotent() -> None:
    adapter = FakeProcessAdapter(live=False)
    manager = make_manager(FakeRuntime(), adapter)
    manager.start()

    first = manager.stop()
    second = manager.stop()

    assert first.state is StreamState.STOPPED
    assert second.state is StreamState.STOPPED
    assert adapter.stop_calls == 1


def test_start_failure_is_sanitized_in_status() -> None:
    adapter = FakeProcessAdapter(live=False, fail_start=True)
    manager = make_manager(FakeRuntime(), adapter)

    with pytest.raises(StreamStartError):
        manager.start()

    status = manager.status()
    assert status.state is StreamState.ERROR
    assert status.whep_url is None
    assert "private ffmpeg stderr" not in (status.error or "")
