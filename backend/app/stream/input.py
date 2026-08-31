from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Literal

from .errors import InputCommandError, InputValidationError

PointerType = Literal["pointer_down", "pointer_move", "pointer_up"]
AllowedKey = Literal["back", "home", "recents"]


@dataclass(frozen=True, slots=True)
class PointerEvent:
    type: PointerType
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class KeyEvent:
    type: Literal["key"]
    key: AllowedKey


InputEvent = PointerEvent | KeyEvent


def _normalized(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputValidationError(f"{name} must be a normalized number")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise InputValidationError(f"{name} must be between 0 and 1")
    return result


def parse_input_event(payload: Any) -> InputEvent:
    if not isinstance(payload, dict):
        raise InputValidationError("input event must be an object")
    event_type = payload.get("type")
    if event_type in {"pointer_down", "pointer_move", "pointer_up"}:
        if set(payload) != {"type", "x", "y"}:
            raise InputValidationError("pointer event schema is invalid")
        return PointerEvent(
            type=event_type,
            x=_normalized(payload.get("x"), "x"),
            y=_normalized(payload.get("y"), "y"),
        )
    if event_type == "key":
        if set(payload) != {"type", "key"}:
            raise InputValidationError("key event schema is invalid")
        key = payload.get("key")
        if key not in {"back", "home", "recents"}:
            raise InputValidationError("unsupported navigation key")
        return KeyEvent(type="key", key=key)
    raise InputValidationError("unsupported input event")


def map_point(x: float, y: float, width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("display dimensions must be positive")
    nx = _normalized(x, "x")
    ny = _normalized(y, "y")
    return round(nx * (width - 1)), round(ny * (height - 1))


class ADBInputAdapter:
    KEYCODES = {"back": "4", "home": "3", "recents": "187"}

    def __init__(
        self,
        *,
        adb_bin: str,
        adb_target: str,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        self._adb_bin = adb_bin
        self._adb_target = adb_target
        self._runner = runner

    def _run(self, *args: str) -> None:
        try:
            result = self._runner(
                [self._adb_bin, "-s", self._adb_target, "shell", "input", *args],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InputCommandError("Android input command failed") from exc
        if result.returncode != 0:
            raise InputCommandError("Android input command failed")

    def tap(self, x: int, y: int) -> None:
        self._run("tap", str(x), str(y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 180) -> None:
        self._run("swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))

    def key(self, key: str) -> None:
        code = self.KEYCODES.get(key)
        if code is None:
            raise InputValidationError("unsupported navigation key")
        self._run("keyevent", code)


class InputService:
    def __init__(self, *, adapter: ADBInputAdapter, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("display dimensions must be positive")
        self._adapter = adapter
        self._width = width
        self._height = height
        self._down: tuple[int, int] | None = None
        self._moved = False

    def handle(self, event: InputEvent) -> None:
        if isinstance(event, KeyEvent):
            self._adapter.key(event.key)
            return

        point = map_point(event.x, event.y, self._width, self._height)
        if event.type == "pointer_down":
            self._down = point
            self._moved = False
            return
        if self._down is None:
            raise InputValidationError("pointer sequence must start with pointer_down")
        if event.type == "pointer_move":
            if point != self._down:
                self._moved = True
            return
        if event.type == "pointer_up":
            start = self._down
            moved = self._moved or point != start
            self._down = None
            self._moved = False
            if moved:
                self._adapter.swipe(start[0], start[1], point[0], point[1])
            else:
                self._adapter.tap(point[0], point[1])
            return
        raise InputValidationError("unsupported input event")
