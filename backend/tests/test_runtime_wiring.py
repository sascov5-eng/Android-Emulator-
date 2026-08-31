from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.main import create_app
import app.runtime as runtime_module


class DummyRuntime:
    pass


def test_create_app_preserves_injected_runtime_service(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    runtime = DummyRuntime()

    app = create_app(settings, runtime_service=runtime)

    assert app.state.runtime_service is runtime


def test_build_runtime_service_uses_configured_adapters(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seen: dict[str, dict[str, object]] = {}

    class FakeDockerDriver:
        def __init__(self, **kwargs) -> None:
            seen["docker"] = kwargs

    class FakeADBClient:
        def __init__(self, **kwargs) -> None:
            seen["adb"] = kwargs

    monkeypatch.setattr(runtime_module, "DockerRuntimeDriver", FakeDockerDriver)
    monkeypatch.setattr(runtime_module, "SubprocessADBClient", FakeADBClient)

    settings = Settings(
        data_dir=tmp_path / "data",
        redroid_image="redroid/redroid:test",
        runtime_name="runtime-name",
        runtime_volume="runtime-volume",
        adb_host="127.0.0.1",
        adb_port=5666,
        boot_timeout_seconds=77,
        adb_bin="my-adb",
        aapt_bin="my-aapt",
        docker_bin="my-docker",
    )

    service = runtime_module.build_runtime_service(settings)

    assert service._boot_timeout_seconds == 77
    assert seen["docker"] == {
        "docker_bin": "my-docker",
        "image": "redroid/redroid:test",
        "runtime_name": "runtime-name",
        "volume_name": "runtime-volume",
        "adb_host": "127.0.0.1",
        "adb_port": 5666,
    }
    assert seen["adb"] == {
        "adb_bin": "my-adb",
        "aapt_bin": "my-aapt",
    }
