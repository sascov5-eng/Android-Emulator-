from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from .config import Settings
from .models import APKRecord
from .storage import APKStorage


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    storage = APKStorage(resolved_settings.data_dir)

    app = FastAPI(title="Android Emulator API", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.apk_storage = storage

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

    return app


app = create_app()
