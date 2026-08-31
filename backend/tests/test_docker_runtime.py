from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.runtime.docker_driver import DockerRuntimeDriver
from app.runtime.errors import RuntimeDriverError


class RecordingRunner:
    def __init__(self, outputs: list[tuple[int, str, str]] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.outputs = list(outputs or [])

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float | None = None,
        check: bool = False,
    ) -> SimpleNamespace:
        assert capture_output is True
        assert text is True
        assert check is False
        self.calls.append(list(args))
        if self.outputs:
            code, stdout, stderr = self.outputs.pop(0)
        else:
            code, stdout, stderr = 0, "", ""
        return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def build_driver(runner: RecordingRunner) -> DockerRuntimeDriver:
    return DockerRuntimeDriver(
        docker_bin="docker",
        image="redroid/redroid:test",
        runtime_name="android-emulator-redroid",
        volume_name="android-emulator-data",
        adb_host="127.0.0.1",
        adb_port=5555,
        runner=runner,
    )


def test_start_creates_privileged_redroid_with_loopback_adb_only() -> None:
    runner = RecordingRunner(
        [
            (1, "", "not found"),
            (0, "container-id\n", ""),
        ]
    )
    driver = build_driver(runner)

    endpoint = driver.start()

    assert endpoint.adb_target == "127.0.0.1:5555"
    assert runner.calls[0] == [
        "docker",
        "inspect",
        "-f",
        "{{.State.Running}}",
        "android-emulator-redroid",
    ]
    assert runner.calls[1] == [
        "docker",
        "run",
        "-d",
        "--rm",
        "--privileged",
        "--name",
        "android-emulator-redroid",
        "-p",
        "127.0.0.1:5555:5555",
        "-v",
        "android-emulator-data:/data",
        "redroid/redroid:test",
    ]
    assert not any("0.0.0.0" in part for part in runner.calls[1])


def test_start_is_idempotent_when_container_is_running() -> None:
    runner = RecordingRunner([(0, "true\n", "")])
    driver = build_driver(runner)

    driver.start()

    assert len(runner.calls) == 1


def test_stop_removes_container_but_preserves_volume() -> None:
    runner = RecordingRunner(
        [
            (0, "true\n", ""),
            (0, "android-emulator-redroid\n", ""),
        ]
    )
    driver = build_driver(runner)

    driver.stop()

    assert runner.calls[-1] == [
        "docker",
        "rm",
        "-f",
        "android-emulator-redroid",
    ]
    assert not any(call[:3] == ["docker", "volume", "rm"] for call in runner.calls)


def test_reset_removes_container_and_volume_then_starts_clean() -> None:
    runner = RecordingRunner(
        [
            (0, "true\n", ""),
            (0, "android-emulator-redroid\n", ""),
            (0, "android-emulator-data\n", ""),
            (0, "new-container\n", ""),
        ]
    )
    driver = build_driver(runner)

    endpoint = driver.reset()

    assert endpoint.adb_target == "127.0.0.1:5555"
    assert ["docker", "volume", "rm", "-f", "android-emulator-data"] in runner.calls
    assert runner.calls[-1][0:3] == ["docker", "run", "-d"]


def test_docker_failure_does_not_leak_stderr() -> None:
    runner = RecordingRunner(
        [
            (1, "", "not found"),
            (1, "", "super secret docker stderr"),
        ]
    )
    driver = build_driver(runner)

    with pytest.raises(RuntimeDriverError) as caught:
        driver.start()

    assert "secret" not in str(caught.value).lower()
