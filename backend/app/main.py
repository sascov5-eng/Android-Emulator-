from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from .config import Settings
from .models import APKRecord
from .runtime import build_runtime_service
from .runtime.errors import (
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
from .runtime.models import AndroidApp, RuntimeStatus
from .storage import APKStorage
from .stream import build_stream_service
from .stream.errors import StreamErrorBase, StreamStartError, StreamStopError, StreamUnavailable
from .stream.models import StreamStatus


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message},
    )


def _runtime_error(exc: RuntimeErrorBase, operation: str) -> JSONResponse:
    if isinstance(exc, RuntimeNotReady):
        return _error("RUNTIME_NOT_READY", "Android runtime is not ready", 409)
    if isinstance(exc, APKNotFound):
        return _error("APK_NOT_FOUND", "APK was not found", 404)
    if isinstance(exc, APKFileMissing):
        return _error("APK_FILE_MISSING", "Stored APK file is missing", 410)
    if isinstance(exc, RuntimeBootTimeout):
        return _error(
            "RUNTIME_BOOT_TIMEOUT",
            "Android runtime did not finish booting in time",
            504,
        )
    if isinstance(exc, AppResolutionError):
        return _error(
            "APP_RESOLUTION_FAILED",
            "Android application metadata could not be resolved",
            422,
        )
    if isinstance(exc, AppLaunchError):
        return _error(
            "APP_LAUNCH_FAILED",
            "Android application failed to launch",
            502,
        )
    if isinstance(exc, ADBCommandError):
        return _error("ADB_COMMAND_FAILED", "Android device command failed", 502)
    if isinstance(exc, RuntimeDriverError):
        mapping = {
            "start": ("RUNTIME_START_FAILED", "Android runtime failed to start"),
            "stop": ("RUNTIME_STOP_FAILED", "Android runtime failed to stop"),
            "reset": ("RUNTIME_RESET_FAILED", "Android runtime failed to reset"),
        }
        code, message = mapping.get(
            operation,
            ("RUNTIME_OPERATION_FAILED", "Android runtime operation failed"),
        )
        return _error(code, message, 502)
    return _error("RUNTIME_OPERATION_FAILED", "Android runtime operation failed", 502)


def _stream_error(exc: Exception, operation: str) -> JSONResponse:
    if isinstance(exc, RuntimeNotReady):
        return _error("RUNTIME_NOT_READY", "Android runtime is not ready", 409)
    if isinstance(exc, StreamUnavailable):
        return _error("STREAM_NOT_AVAILABLE", "Android stream is not available", 503)
    if isinstance(exc, StreamStartError):
        return _error("STREAM_START_FAILED", "Android stream failed to start", 502)
    if isinstance(exc, StreamStopError):
        return _error("STREAM_STOP_FAILED", "Android stream failed to stop", 502)
    return _error("STREAM_OPERATION_FAILED", "Android stream operation failed", 502)


def create_app(
    settings: Settings | None = None,
    *,
    runtime_service: Any | None = None,
    stream_service: Any | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    storage = APKStorage(resolved_settings.data_dir)
    runtime = runtime_service or build_runtime_service(resolved_settings)
    stream = stream_service or build_stream_service(resolved_settings, runtime)

    app = FastAPI(title="Android Emulator API", version="0.3.0")
    app.state.settings = resolved_settings
    app.state.apk_storage = storage
    app.state.runtime_service = runtime
    app.state.stream_service = stream

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/apks", response_model=list[APKRecord])
    def list_apks() -> list[APKRecord]:
        return storage.list_apks()

    @app.post("/v1/apks", response_model=APKRecord, status_code=201)
    async def upload_apk(file: UploadFile = File(...)) -> APKRecord | JSONResponse:
        filename = file.filename or ""
        if Path(filename).suffix.lower() != ".apk":
            await file.close()
            return _error("APK_INVALID", "Only .apk files are accepted", 400)

        try:
            data = await file.read(resolved_settings.max_apk_bytes + 1)
        finally:
            await file.close()

        if len(data) > resolved_settings.max_apk_bytes:
            return _error("APK_TOO_LARGE", "APK exceeds the configured size limit", 413)

        return storage.save_upload(filename, data)

    @app.get("/v1/runtime/status", response_model=RuntimeStatus)
    def runtime_status() -> RuntimeStatus | JSONResponse:
        try:
            return runtime.status()
        except RuntimeErrorBase as exc:
            return _runtime_error(exc, "status")

    @app.post("/v1/runtime/start", response_model=RuntimeStatus)
    def runtime_start() -> RuntimeStatus | JSONResponse:
        try:
            return runtime.start()
        except RuntimeErrorBase as exc:
            return _runtime_error(exc, "start")

    @app.post("/v1/runtime/stop", response_model=RuntimeStatus)
    def runtime_stop() -> RuntimeStatus | JSONResponse:
        try:
            return runtime.stop()
        except RuntimeErrorBase as exc:
            return _runtime_error(exc, "stop")

    @app.post("/v1/runtime/reset", response_model=RuntimeStatus)
    def runtime_reset() -> RuntimeStatus | JSONResponse:
        try:
            return runtime.reset()
        except RuntimeErrorBase as exc:
            return _runtime_error(exc, "reset")

    @app.post("/v1/runtime/install/{apk_id}", response_model=AndroidApp)
    def runtime_install(apk_id: str) -> AndroidApp | JSONResponse:
        try:
            return runtime.install(apk_id, storage)
        except RuntimeErrorBase as exc:
            return _runtime_error(exc, "install")

    @app.post("/v1/runtime/launch/{apk_id}", response_model=AndroidApp)
    def runtime_launch(apk_id: str) -> AndroidApp | JSONResponse:
        try:
            return runtime.launch(apk_id, storage)
        except RuntimeErrorBase as exc:
            return _runtime_error(exc, "launch")

    @app.get("/v1/runtime/apps", response_model=list[AndroidApp])
    def runtime_apps() -> list[AndroidApp] | JSONResponse:
        try:
            return runtime.list_apps()
        except RuntimeErrorBase as exc:
            return _runtime_error(exc, "apps")

    @app.get("/v1/stream/status", response_model=StreamStatus)
    def stream_status() -> StreamStatus | JSONResponse:
        try:
            return stream.status()
        except (RuntimeErrorBase, StreamErrorBase) as exc:
            return _stream_error(exc, "status")

    @app.post("/v1/stream/start", response_model=StreamStatus)
    def stream_start() -> StreamStatus | JSONResponse:
        try:
            return stream.start()
        except (RuntimeErrorBase, StreamErrorBase) as exc:
            return _stream_error(exc, "start")

    @app.post("/v1/stream/stop", response_model=StreamStatus)
    def stream_stop() -> StreamStatus | JSONResponse:
        try:
            return stream.stop()
        except (RuntimeErrorBase, StreamErrorBase) as exc:
            return _stream_error(exc, "stop")

    return app


app = create_app()
