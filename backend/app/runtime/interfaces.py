from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import AndroidApp, RuntimeEndpoint


class RuntimeDriver(Protocol):
    def start(self) -> RuntimeEndpoint: ...

    def stop(self) -> None: ...

    def exists(self) -> bool: ...

    def reset(self) -> RuntimeEndpoint: ...


class ADBClient(Protocol):
    def wait_for_device(self, target: str, timeout_seconds: float) -> None: ...

    def wait_for_boot(self, target: str, timeout_seconds: float) -> None: ...

    def install(self, target: str, apk_path: Path) -> None: ...

    def resolve_launchable(self, target: str, apk_path: Path) -> AndroidApp: ...

    def launch(
        self,
        target: str,
        package_name: str,
        activity_name: str | None,
    ) -> None: ...

    def list_apps(self, target: str) -> list[AndroidApp]: ...
