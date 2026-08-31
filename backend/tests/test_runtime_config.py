from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings


def test_runtime_settings_default_to_loopback_adb(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")

    assert settings.adb_host == "127.0.0.1"
    assert settings.adb_port == 5555
    assert settings.boot_timeout_seconds == 120.0
    assert settings.runtime_driver == "docker"


def test_runtime_settings_reject_public_adb_binding(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="loopback"):
        Settings(data_dir=tmp_path / "data", adb_host="0.0.0.0")


@pytest.mark.parametrize("host", ["192.168.1.20", "10.0.0.2", "::"])
def test_runtime_settings_reject_non_loopback_adb_hosts(
    tmp_path: Path,
    host: str,
) -> None:
    with pytest.raises(ValueError, match="loopback"):
        Settings(data_dir=tmp_path / "data", adb_host=host)


def test_runtime_settings_validate_port_and_timeout(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="adb_port"):
        Settings(data_dir=tmp_path / "data", adb_port=0)
    with pytest.raises(ValueError, match="boot_timeout"):
        Settings(data_dir=tmp_path / "data", boot_timeout_seconds=0)
