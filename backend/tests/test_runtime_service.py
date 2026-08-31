from __future__ import annotations

import pytest

from app.runtime.errors import RuntimeBootTimeout
from app.runtime.models import RuntimeEndpoint, RuntimeState
from app.runtime.service import RuntimeService


class FakeRuntimeDriver:
    def __init__(self) -> None:
        self.endpoint = RuntimeEndpoint(adb_host="127.0.0.1", adb_port=5555)
        self.running = False
        self.start_calls = 0
        self.stop_calls = 0
        self.reset_calls = 0

    def start(self) -> RuntimeEndpoint:
        self.start_calls += 1
        self.running = True
        return self.endpoint

    def stop(self) -> None:
        self.stop_calls += 1
        self.running = False

    def exists(self) -> bool:
        return self.running

    def reset(self) -> RuntimeEndpoint:
        self.reset_calls += 1
        self.running = True
        return self.endpoint


class FakeADBClient:
    def __init__(self) -> None:
        self.device_waits: list[tuple[str, float]] = []
        self.boot_waits: list[tuple[str, float]] = []
        self.boot_error: Exception | None = None

    def wait_for_device(self, target: str, timeout_seconds: float) -> None:
        self.device_waits.append((target, timeout_seconds))

    def wait_for_boot(self, target: str, timeout_seconds: float) -> None:
        self.boot_waits.append((target, timeout_seconds))
        if self.boot_error is not None:
            raise self.boot_error

    def install(self, target, apk_path):  # pragma: no cover - not used here
        raise AssertionError("not expected")

    def resolve_launchable(self, target, apk_path):  # pragma: no cover
        raise AssertionError("not expected")

    def launch(self, target, package_name, activity_name):  # pragma: no cover
        raise AssertionError("not expected")

    def list_apps(self, target):  # pragma: no cover
        raise AssertionError("not expected")


def build_service() -> tuple[RuntimeService, FakeRuntimeDriver, FakeADBClient]:
    driver = FakeRuntimeDriver()
    adb = FakeADBClient()
    service = RuntimeService(driver=driver, adb=adb, boot_timeout_seconds=12.5)
    return service, driver, adb


def test_start_waits_for_boot_and_becomes_ready() -> None:
    service, driver, adb = build_service()

    status = service.start()

    assert status.state is RuntimeState.READY
    assert status.adb_target == "127.0.0.1:5555"
    assert driver.start_calls == 1
    assert adb.device_waits == [("127.0.0.1:5555", 12.5)]
    assert adb.boot_waits == [("127.0.0.1:5555", 12.5)]


def test_start_is_idempotent_when_ready() -> None:
    service, driver, adb = build_service()
    service.start()

    second = service.start()

    assert second.state is RuntimeState.READY
    assert driver.start_calls == 1
    assert len(adb.boot_waits) == 1


def test_boot_timeout_moves_service_to_error() -> None:
    service, _, adb = build_service()
    adb.boot_error = RuntimeBootTimeout("Android boot timed out")

    with pytest.raises(RuntimeBootTimeout):
        service.start()

    status = service.status()
    assert status.state is RuntimeState.ERROR
    assert status.error == "Android boot timed out"


def test_stop_is_idempotent() -> None:
    service, driver, _ = build_service()

    first = service.stop()
    assert first.state is RuntimeState.STOPPED
    assert driver.stop_calls == 0

    service.start()
    second = service.stop()
    third = service.stop()

    assert second.state is RuntimeState.STOPPED
    assert third.state is RuntimeState.STOPPED
    assert driver.stop_calls == 1


def test_reset_calls_driver_reset_and_waits_for_boot() -> None:
    service, driver, adb = build_service()

    status = service.reset()

    assert status.state is RuntimeState.READY
    assert driver.reset_calls == 1
    assert adb.device_waits == [("127.0.0.1:5555", 12.5)]
    assert adb.boot_waits == [("127.0.0.1:5555", 12.5)]
