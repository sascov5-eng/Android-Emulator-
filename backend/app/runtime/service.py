from __future__ import annotations

from .errors import RuntimeBootTimeout, RuntimeDriverError
from .interfaces import ADBClient, RuntimeDriver
from .models import RuntimeEndpoint, RuntimeState, RuntimeStatus


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
        self._installed: dict[str, object] = {}

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
