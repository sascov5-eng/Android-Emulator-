from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.runtime.errors import (
    ADBCommandError,
    APKFileMissing,
    APKNotFound,
    AppLaunchError,
    AppResolutionError,
    RuntimeBootTimeout,
    RuntimeDriverError,
    RuntimeNotReady,
)
from app.runtime.models import AndroidApp, RuntimeState, RuntimeStatus


class FakeRuntimeService:
    def __init__(self) -> None:
        self.current = RuntimeStatus(state=RuntimeState.STOPPED)
        self.error_for: dict[str, Exception] = {}
        self.install_args: tuple[str, object] | None = None
        self.launch_args: tuple[str, object] | None = None
        self.apps = [AndroidApp(package_name="com.example.game", activity_name=".MainActivity")]

    def _raise_for(self, operation: str) -> None:
        error = self.error_for.get(operation)
        if error is not None:
            raise error

    def status(self) -> RuntimeStatus:
        self._raise_for("status")
        return self.current

    def start(self) -> RuntimeStatus:
        self._raise_for("start")
        self.current = RuntimeStatus(
            state=RuntimeState.READY,
            adb_target="127.0.0.1:5555",
        )
        return self.current

    def stop(self) -> RuntimeStatus:
        self._raise_for("stop")
        self.current = RuntimeStatus(state=RuntimeState.STOPPED)
        return self.current

    def reset(self) -> RuntimeStatus:
        self._raise_for("reset")
        self.current = RuntimeStatus(
            state=RuntimeState.READY,
            adb_target="127.0.0.1:5555",
        )
        return self.current

    def install(self, apk_id: str, storage: object) -> AndroidApp:
        self._raise_for("install")
        self.install_args = (apk_id, storage)
        return self.apps[0]

    def launch(self, apk_id: str, storage: object) -> AndroidApp:
        self._raise_for("launch")
        self.launch_args = (apk_id, storage)
        return self.apps[0]

    def list_apps(self) -> list[AndroidApp]:
        self._raise_for("apps")
        return list(self.apps)


def make_client(tmp_path: Path) -> tuple[TestClient, FakeRuntimeService]:
    settings = Settings(data_dir=tmp_path / "data", max_apk_bytes=1024)
    runtime = FakeRuntimeService()
    app = create_app(settings, runtime_service=runtime)
    return TestClient(app), runtime


def test_runtime_lifecycle_endpoints(tmp_path: Path) -> None:
    client, runtime = make_client(tmp_path)

    assert client.get("/v1/runtime/status").json()["state"] == "stopped"
    assert client.post("/v1/runtime/start").json()["state"] == "ready"
    assert client.post("/v1/runtime/reset").json()["state"] == "ready"
    assert client.post("/v1/runtime/stop").json()["state"] == "stopped"
    assert runtime.current.state is RuntimeState.STOPPED


def test_install_and_launch_routes_receive_backend_storage(tmp_path: Path) -> None:
    client, runtime = make_client(tmp_path)

    install = client.post("/v1/runtime/install/apk-123")
    launch = client.post("/v1/runtime/launch/apk-123")

    assert install.status_code == 200
    assert install.json()["package_name"] == "com.example.game"
    assert launch.status_code == 200
    assert runtime.install_args is not None
    assert runtime.install_args[0] == "apk-123"
    assert runtime.launch_args is not None
    assert runtime.launch_args[0] == "apk-123"
    assert runtime.install_args[1] is runtime.launch_args[1]


def test_apps_route_returns_android_apps(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

    response = client.get("/v1/runtime/apps")

    assert response.status_code == 200
    assert response.json() == [
        {
            "package_name": "com.example.game",
            "activity_name": ".MainActivity",
            "label": None,
        }
    ]


@pytest.mark.parametrize(
    ("operation", "method", "path", "error", "status_code", "code"),
    [
        (
            "apps",
            "get",
            "/v1/runtime/apps",
            RuntimeNotReady("not ready"),
            409,
            "RUNTIME_NOT_READY",
        ),
        (
            "install",
            "post",
            "/v1/runtime/install/missing",
            APKNotFound("missing"),
            404,
            "APK_NOT_FOUND",
        ),
        (
            "install",
            "post",
            "/v1/runtime/install/missing-file",
            APKFileMissing("missing file"),
            410,
            "APK_FILE_MISSING",
        ),
        (
            "start",
            "post",
            "/v1/runtime/start",
            RuntimeBootTimeout("secret timeout detail"),
            504,
            "RUNTIME_BOOT_TIMEOUT",
        ),
        (
            "start",
            "post",
            "/v1/runtime/start",
            RuntimeDriverError("docker stderr secret"),
            502,
            "RUNTIME_START_FAILED",
        ),
        (
            "install",
            "post",
            "/v1/runtime/install/apk",
            ADBCommandError("adb stderr secret"),
            502,
            "ADB_COMMAND_FAILED",
        ),
        (
            "install",
            "post",
            "/v1/runtime/install/apk",
            AppResolutionError("package parser secret"),
            422,
            "APP_RESOLUTION_FAILED",
        ),
        (
            "launch",
            "post",
            "/v1/runtime/launch/apk",
            AppLaunchError("launch stderr secret"),
            502,
            "APP_LAUNCH_FAILED",
        ),
    ],
)
def test_runtime_errors_use_stable_public_envelope(
    tmp_path: Path,
    operation: str,
    method: str,
    path: str,
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    client, runtime = make_client(tmp_path)
    runtime.error_for[operation] = error

    response = getattr(client, method)(path)

    assert response.status_code == status_code
    body = response.json()
    assert body["code"] == code
    assert "secret" not in body["message"].lower()
