from __future__ import annotations

from dataclasses import dataclass
import math

import pytest

from app.stream.errors import InputCommandError, InputValidationError
from app.stream.input import ADBInputAdapter, InputService, map_point, parse_input_event


@dataclass
class Result:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class Runner:
    def __init__(self, *, returncode: int = 0) -> None:
        self.returncode = returncode
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), dict(kwargs)))
        return Result(returncode=self.returncode, stderr="private adb stderr")


@pytest.mark.parametrize("value", [-0.01, 1.01, math.inf, -math.inf, math.nan])
def test_pointer_coordinates_must_be_finite_and_normalized(value: float) -> None:
    with pytest.raises(InputValidationError):
        parse_input_event({"type": "pointer_down", "x": value, "y": 0.5})


def test_map_point_uses_full_android_pixel_range() -> None:
    assert map_point(0.0, 0.0, 720, 1280) == (0, 0)
    assert map_point(1.0, 1.0, 720, 1280) == (719, 1279)
    assert map_point(0.5, 0.5, 720, 1280) == (360, 640)


@pytest.mark.parametrize("key", ["volume_up", "power", "4", "KEYCODE_HOME", "shell rm -rf /"])
def test_only_navigation_keys_are_allowed(key: str) -> None:
    with pytest.raises(InputValidationError):
        parse_input_event({"type": "key", "key": key})


def test_unknown_event_type_is_rejected() -> None:
    with pytest.raises(InputValidationError):
        parse_input_event({"type": "shell", "command": "id"})


def test_adb_key_events_use_allowlisted_keycodes_and_no_shell() -> None:
    runner = Runner()
    adapter = ADBInputAdapter(adb_bin="adb", adb_target="127.0.0.1:5555", runner=runner)

    adapter.key("back")
    adapter.key("home")
    adapter.key("recents")

    assert [call[0] for call in runner.calls] == [
        ["adb", "-s", "127.0.0.1:5555", "shell", "input", "keyevent", "4"],
        ["adb", "-s", "127.0.0.1:5555", "shell", "input", "keyevent", "3"],
        ["adb", "-s", "127.0.0.1:5555", "shell", "input", "keyevent", "187"],
    ]
    assert all(call[1].get("shell") is False for call in runner.calls)


def test_pointer_down_up_becomes_tap() -> None:
    runner = Runner()
    service = InputService(
        adapter=ADBInputAdapter(adb_bin="adb", adb_target="127.0.0.1:5555", runner=runner),
        width=720,
        height=1280,
    )

    service.handle(parse_input_event({"type": "pointer_down", "x": 0.25, "y": 0.5}))
    service.handle(parse_input_event({"type": "pointer_up", "x": 0.25, "y": 0.5}))

    assert runner.calls[-1][0] == [
        "adb", "-s", "127.0.0.1:5555", "shell", "input", "tap", "180", "640"
    ]


def test_pointer_move_then_up_becomes_swipe() -> None:
    runner = Runner()
    service = InputService(
        adapter=ADBInputAdapter(adb_bin="adb", adb_target="127.0.0.1:5555", runner=runner),
        width=720,
        height=1280,
    )

    service.handle(parse_input_event({"type": "pointer_down", "x": 0.1, "y": 0.2}))
    service.handle(parse_input_event({"type": "pointer_move", "x": 0.4, "y": 0.6}))
    service.handle(parse_input_event({"type": "pointer_up", "x": 0.5, "y": 0.7}))

    assert runner.calls[-1][0] == [
        "adb", "-s", "127.0.0.1:5555", "shell", "input", "swipe",
        "72", "256", "360", "895", "180",
    ]


def test_move_or_up_without_down_is_rejected() -> None:
    service = InputService(
        adapter=ADBInputAdapter(adb_bin="adb", adb_target="127.0.0.1:5555", runner=Runner()),
        width=720,
        height=1280,
    )

    with pytest.raises(InputValidationError):
        service.handle(parse_input_event({"type": "pointer_move", "x": 0.2, "y": 0.2}))


def test_adb_failure_does_not_leak_stderr() -> None:
    adapter = ADBInputAdapter(adb_bin="adb", adb_target="127.0.0.1:5555", runner=Runner(returncode=1))

    with pytest.raises(InputCommandError) as caught:
        adapter.key("home")

    assert "private adb stderr" not in str(caught.value)
