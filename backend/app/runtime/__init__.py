from __future__ import annotations

from ..config import Settings
from .adb import SubprocessADBClient
from .docker_driver import DockerRuntimeDriver
from .errors import (
    ADBCommandError,
    APKFileMissing,
    APKNotFound,
    AppLaunchError,
    AppResolutionError,
    RuntimeBootTimeout,
    RuntimeDriverError,
    RuntimeErrorBase,
    RuntimeNotReady,
)
from .models import AndroidApp, RuntimeEndpoint, RuntimeState, RuntimeStatus
from .service import RuntimeService


def build_runtime_service(settings: Settings) -> RuntimeService:
    driver = DockerRuntimeDriver(
        docker_bin=settings.docker_bin,
        image=settings.redroid_image,
        runtime_name=settings.runtime_name,
        volume_name=settings.runtime_volume,
        adb_host=settings.adb_host,
        adb_port=settings.adb_port,
    )
    adb = SubprocessADBClient(
        adb_bin=settings.adb_bin,
        aapt_bin=settings.aapt_bin,
    )
    return RuntimeService(
        driver=driver,
        adb=adb,
        boot_timeout_seconds=settings.boot_timeout_seconds,
    )


__all__ = [
    "ADBCommandError",
    "APKFileMissing",
    "APKNotFound",
    "AndroidApp",
    "AppLaunchError",
    "AppResolutionError",
    "DockerRuntimeDriver",
    "RuntimeBootTimeout",
    "RuntimeDriverError",
    "RuntimeEndpoint",
    "RuntimeErrorBase",
    "RuntimeNotReady",
    "RuntimeService",
    "RuntimeState",
    "RuntimeStatus",
    "SubprocessADBClient",
    "build_runtime_service",
]
