from __future__ import annotations

from pathlib import Path

from ..storage import APKStorage
from .errors import (
    ADBCommandError,
    APKFileMissing,
    APKNotFound,
    AppLaunchError,
    RuntimeBootTimeout,
    RuntimeDriverError,
    RuntimeNotReady,
)
from .interfaces import ADBClient, RuntimeDriver
from .models import AndroidApp, RuntimeEndpoint, RuntimeState, RuntimeStatus


class RuntimeService:
    def __init__(
        self,
        *,
        driver: RuntimeDriver,
        adb: ADBClient,
        boot_timeout_seconds: float,
    ) -> None:
        if boot_timeout_seconds <= 0:
            raise ValueError("boot_timeout_seconds must be positive")
        self._driver = driver
        self._adb = adb
        self._boot_timeout_seconds = boot_timeout_seconds
        self._endpoint: RuntimeEndpoint | None = None
        self._status = RuntimeStatus(state=RuntimeState.STOPPED)
        self._installed: dict[str, AndroidApp] = {}

    def status(self) -> RuntimeStatus:
        return self._status.model_copy(deep=True)

    def _wait_until_ready(self, endpoint: RuntimeEndpoint) -> RuntimeStatus:
        target = endpoint.adb_target
        self._adb.wait_for_device(target, self._boot_timeout_seconds)
        self._adb.wait_for_boot(target, self._boot_timeout_seconds)
        self._endpoint = endpoint
        self._status = RuntimeStatus(
            state=RuntimeState.READY,
            adb_target=target,
        )
        return self.status()

    def _mark_error(self, exc: Exception) -> None:
        self._status = RuntimeStatus(
            state=RuntimeState.ERROR,
            adb_target=self._endpoint.adb_target if self._endpoint else None,
            error=str(exc),
        )

    def _require_ready(self) -> str:
        if self._status.state is not RuntimeState.READY or self._endpoint is None:
            raise RuntimeNotReady("Android runtime is not ready")
        return self._endpoint.adb_target

    @staticmethod
    def _resolve_apk_path(apk_id: str, storage: APKStorage) -> Path:
        record = storage.get_apk(apk_id)
        if record is None:
            raise APKNotFound("APK was not found")

        path = storage.path_for(apk_id)
        if path is None or not path.is_file():
            raise APKFileMissing("Stored APK file is missing")
        return path

    def start(self) -> RuntimeStatus:
        if self._status.state is RuntimeState.READY:
            return self.status()

        self._status = RuntimeStatus(state=RuntimeState.STARTING)
        try:
            endpoint = self._driver.start()
            return self._wait_until_ready(endpoint)
        except (RuntimeBootTimeout, RuntimeDriverError) as exc:
            self._mark_error(exc)
            raise
        except Exception as exc:
            wrapped = RuntimeDriverError("Android runtime failed to start")
            self._mark_error(wrapped)
            raise wrapped from exc

    def stop(self) -> RuntimeStatus:
        if self._status.state is RuntimeState.STOPPED and not self._driver.exists():
            return self.status()

        self._status = RuntimeStatus(
            state=RuntimeState.STOPPING,
            adb_target=self._endpoint.adb_target if self._endpoint else None,
        )
        try:
            if self._driver.exists():
                self._driver.stop()
        except RuntimeDriverError as exc:
            self._mark_error(exc)
            raise
        except Exception as exc:
            wrapped = RuntimeDriverError("Android runtime failed to stop")
            self._mark_error(wrapped)
            raise wrapped from exc

        self._endpoint = None
        self._installed.clear()
        self._status = RuntimeStatus(state=RuntimeState.STOPPED)
        return self.status()

    def reset(self) -> RuntimeStatus:
        self._status = RuntimeStatus(state=RuntimeState.STARTING)
        self._installed.clear()
        self._endpoint = None
        try:
            endpoint = self._driver.reset()
            return self._wait_until_ready(endpoint)
        except (RuntimeBootTimeout, RuntimeDriverError) as exc:
            self._mark_error(exc)
            raise
        except Exception as exc:
            wrapped = RuntimeDriverError("Android runtime failed to reset")
            self._mark_error(wrapped)
            raise wrapped from exc

    def install(self, apk_id: str, storage: APKStorage) -> AndroidApp:
        target = self._require_ready()
        path = self._resolve_apk_path(apk_id, storage)
        self._adb.install(target, path)
        app = self._adb.resolve_launchable(target, path)
        self._installed[apk_id] = app
        return app

    def launch(self, apk_id: str, storage: APKStorage) -> AndroidApp:
        target = self._require_ready()
        path = self._resolve_apk_path(apk_id, storage)
        app = self._installed.get(apk_id)
        if app is None:
            app = self._adb.resolve_launchable(target, path)
            self._installed[apk_id] = app

        try:
            self._adb.launch(target, app.package_name, app.activity_name)
        except AppLaunchError:
            raise
        except ADBCommandError as exc:
            raise AppLaunchError("Android application failed to launch") from exc
        return app

    def list_apps(self) -> list[AndroidApp]:
        target = self._require_ready()
        return self._adb.list_apps(target)
