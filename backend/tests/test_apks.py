from pathlib import Path

from fastapi.testclient import TestClient


def _valid_apk_bytes(extra: bytes = b"demo") -> bytes:
    return b"PK\x03\x04" + extra


def test_upload_apk_returns_metadata(client: TestClient) -> None:
    response = client.post(
        "/v1/apks",
        files={"file": ("demo.apk", _valid_apk_bytes(), "application/vnd.android.package-archive")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["original_filename"] == "demo.apk"
    assert payload["size_bytes"] == len(_valid_apk_bytes())
    assert len(payload["sha256"]) == 64
    assert payload["id"]
    assert payload["created_at"]
    assert "storage_path" not in payload


def test_upload_rejects_non_apk(client: TestClient) -> None:
    response = client.post(
        "/v1/apks",
        files={"file": ("demo.txt", b"not an apk", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "APK_INVALID"


def test_upload_rejects_file_above_limit(client: TestClient) -> None:
    response = client.post(
        "/v1/apks",
        files={"file": ("large.apk", b"x" * 1025, "application/vnd.android.package-archive")},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "APK_TOO_LARGE"


def test_list_apks_returns_previous_upload(client: TestClient) -> None:
    upload = client.post(
        "/v1/apks",
        files={"file": ("first.apk", _valid_apk_bytes(b"first"), "application/vnd.android.package-archive")},
    )
    assert upload.status_code == 201

    response = client.get("/v1/apks")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == upload.json()["id"]
    assert items[0]["original_filename"] == "first.apk"


def test_storage_does_not_use_original_filename_as_path(tmp_path: Path) -> None:
    from app.storage import APKStorage

    root = tmp_path / "data"
    storage = APKStorage(root)

    record = storage.save_upload("../../escape.apk", _valid_apk_bytes())

    assert record.original_filename == "../../escape.apk"
    assert not (tmp_path / "escape.apk").exists()
    apk_files = list((root / "apks").glob("*.apk"))
    assert len(apk_files) == 1
    assert apk_files[0].name != "escape.apk"
