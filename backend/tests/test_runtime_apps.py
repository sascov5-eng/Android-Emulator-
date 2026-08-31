from __future__ import annotations

from pathlib import Path

import pytest

from app.runtime.errors import APKFileMissing, APKNotFound, RuntimeNotReady
from app.runtime.models import AndroidApp, RuntimeEndpoint
from app.runtime.service import RuntimeService
from app.storage import APKStorage


class FakeRuntimeDriver:
    def __init__(self) -> None:
        self.running = False
        self.endpoint = RuntimeEndpoint(adb_host="127.0.0.1", adb_port=5555)

    def start(self) -> RuntimeEndpoint:
        self.running = True
        return self.endpoint

    def stop(self) -> None:
        self.running = False

    def exists(self) -> bool:
        return self.running

    def reset(self) -> RuntimeEndpoint:
        self.running = True
        return self.endpoint


class FakeADBClient:
    def __init__(self) -> None:
        self.installs: list[tuple[str, Path]] = []
        self.launches: list[tuple[str, str, str | None]] = []
        self.resolutions: list[tuple[str, Path]] = []
        self.apps = [AndroidApp(package_name="com.example.game", activity_name=".MainActivity")]

    def wait_for_device(self, target: str, timeout_seconds: float) -> None:
        return None

    def wait_for_boot(self, target: str, timeout_seconds: float) -> None:
        return None

    def install(self, target: str, apk_path: Path) -> None:
        self.installs.append((target, apk_path))

    def resolve_launchable(self, target: str, apk_path: Path) -> AndroidApp:
        self.resolutions.append((target, apk_path))
        return self.apps[0]

    def launch(self, target: str, package_name: str, activity_name: str | None) -> None:
        self.launches.append((target, package_name, activity_name))

    def list_apps(self, target: str) -> list[AndroidApp]:
        return list(self.apps)


def build_service() -> tuple[RuntimeService, FakeADBClient]:
    adb = FakeADBClient()
    service = RuntimeService(
        driver=FakeRuntimeDriver(),
        adb=adb,
        boot_timeout_seconds=5,
    )
    return service, adb


def test_install_requires_ready_runtime(tmp_path: Path) -> None:
    storage = APKStorage(tmp_path / "data")
    record = storage.save_upload("game.apk", b"apk")
    service, _ = build_service()

    with pytest.raises(RuntimeNotReady):
        service.install(record.id, storage)


def test_install_rejects_unknown_apk(tmp_path: Path) -> None:
    storage = APKStorage(tmp_path / "data")
    service, _ = build_service()
    service.start()

    with pytest.raises(APKNotFound):
        service.install("missing-apk", storage)


def test_install_rejects_missing_storage_file(tmp_path: Path) -> None:
    storage = APKStorage(tmp_path / "data")
    record = storage.save_upload("game.apk", b"apk")
    stored_path = storage.apk_dir / f"{record.id}.apk"
    stored_path.unlink()
    service, _ = build_service()
    service.start()

    with pytest.raises(APKFileMissing):
        service.install(record.id, storage)


def test_install_uses_storage_path_and_returns_resolved_app(tmp_path: Path) -> None:
    storage = APKStorage(tmp_path / "data")
    record = storage.save_upload("game.apk", b"apk")
    service, adb = build_service()
    service.start()

    app = service.install(record.id, storage)

    expected_path = storage.apk_dir / f"{record.id}.apk"
    assert app.package_name == "com.example.game"
    assert adb.installs == [("127.0.0.1:5555", expected_path)]
    assert adb.resolutions == [("127.0.0.1:5555", expected_path)]


def test_launch_uses_installed_package_and_activity(tmp_path: Path) -> None:
    storage = APKStorage(tmp_path / "data")
    record = storage.save_upload("game.apk", b"apk")
    service, adb = build_service()
    service.start()
    service.install(record.id, storage)

    launched = service.launch(record.id, storage)

    assert launched.package_name == "com.example.game"
    assert adb.launches == [
        ("127.0.0.1:5555", "com.example.game", ".MainActivity")
    ]


def test_list_apps_requires_ready_runtime() -> None:
    service, _ = build_service()

    with pytest.raises(RuntimeNotReady):
        service.list_apps()


def test_list_apps_returns_adb_apps_when_ready() -> None:
    service, _ = build_service()
    service.start()

    apps = service.list_apps()

    assert [app.package_name for app in apps] == ["com.example.game"]
