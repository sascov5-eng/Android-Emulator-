# Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working repository foundation: a tested FastAPI backend, a SwiftUI iOS shell that can pick and upload APK files, and GitHub Actions that produce an unsigned/re-signable `.ipa` artifact without a local PC.

**Architecture:** The iOS app communicates with a small FastAPI service over HTTPS. Phase 1 implements APK intake and local metadata persistence while keeping Android runtime/streaming behind future interfaces. The iOS project is generated with XcodeGen and built on a GitHub-hosted macOS runner with code signing disabled, then packaged as `Payload/AndroidEmulator.app` inside an `.ipa` for later signing by the user.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLite, pytest, Swift 6, SwiftUI, URLSession, XcodeGen, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-31-android-emulator-mvp-design.md`

## Global Constraints

- iOS client: Swift 6 / SwiftUI.
- Backend: Python 3.12 + FastAPI.
- APKs are untrusted input; filenames must never become filesystem paths directly.
- ADB is not exposed in Phase 1.
- Secrets must not be committed.
- First release path is a downloadable `.ipa` artifact from GitHub Actions.
- App Store distribution is out of scope for this phase.
- Running Android locally inside iOS is out of scope.

---

## File map

### Backend

- `backend/pyproject.toml` — dependencies and pytest configuration.
- `backend/app/__init__.py` — package marker.
- `backend/app/config.py` — environment-backed paths and upload limits.
- `backend/app/models.py` — API response models.
- `backend/app/storage.py` — SQLite metadata and safe APK file persistence.
- `backend/app/main.py` — FastAPI app and HTTP routes.
- `backend/tests/conftest.py` — isolated test app/storage fixture.
- `backend/tests/test_health.py` — health endpoint behavior.
- `backend/tests/test_apks.py` — APK validation/upload/list behavior.

### iOS

- `ios/project.yml` — XcodeGen project definition.
- `ios/AndroidEmulator/App/AndroidEmulatorApp.swift` — app entry point.
- `ios/AndroidEmulator/Models/APKItem.swift` — backend APK model.
- `ios/AndroidEmulator/Networking/APIClient.swift` — health/list/upload client.
- `ios/AndroidEmulator/ViewModels/LibraryViewModel.swift` — library/upload state.
- `ios/AndroidEmulator/Views/LibraryView.swift` — main APK library and file picker UI.
- `ios/AndroidEmulator/Views/SettingsView.swift` — editable backend URL stored in `AppStorage`.
- `ios/AndroidEmulator/Info.plist` — app metadata and local-network-friendly transport settings for development.
- `ios/AndroidEmulatorTests/APIClientTests.swift` — model/URL construction tests that do not require a real backend.

### Automation/docs

- `.github/workflows/backend-ci.yml` — Python tests.
- `.github/workflows/build-ios.yml` — generate Xcode project, build device `.app`, package unsigned `.ipa`, upload artifact.
- `.gitignore` — Python, Xcode and runtime-generated files.
- `.env.example` — backend environment variables.
- `README.md` — build/use instructions and Phase 1 limitations.

---

### Task 1: Backend health endpoint and configuration

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `create_app(settings: Settings | None = None) -> FastAPI`
- Produces: `Settings(data_dir: Path, max_apk_bytes: int)`
- HTTP: `GET /health -> {"status":"ok"}`

- [ ] **Step 1: Write the failing health test**

```python
from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `cd backend && python -m pytest tests/test_health.py -v`
Expected: FAIL because `app.main` / `create_app` does not exist yet.

- [ ] **Step 3: Implement minimal app factory and settings**

`Settings` reads `ANDROID_EMULATOR_DATA_DIR` with default `./data` and `ANDROID_EMULATOR_MAX_APK_BYTES` with default `536870912` (512 MiB). `create_app()` stores settings on `app.state.settings` and exposes `/health`.

- [ ] **Step 4: Run health test and full backend suite**

Run: `cd backend && python -m pytest -v`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add backend health foundation`

---

### Task 2: APK upload validation and persistence

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/app/storage.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_apks.py`

**Interfaces:**
- Produces: `APKRecord(id: str, original_filename: str, sha256: str, size_bytes: int, created_at: datetime)`
- Produces: `APKStorage(root: Path)` with `save_upload(filename: str, data: bytes) -> APKRecord` and `list_apks() -> list[APKRecord]`.
- HTTP: `POST /v1/apks` multipart field `file`.
- HTTP: `GET /v1/apks` returns JSON array of APK records.
- Error: invalid extension returns HTTP 400 with `{"code":"APK_INVALID", ...}`.
- Error: over size limit returns HTTP 413 with `{"code":"APK_TOO_LARGE", ...}`.

- [ ] **Step 1: Write failing upload tests**

Tests must cover:

```python
def test_upload_apk_returns_metadata(client): ...
def test_upload_rejects_non_apk(client): ...
def test_upload_rejects_file_above_limit(client): ...
def test_list_apks_returns_previous_upload(client): ...
def test_storage_does_not_use_original_filename_as_path(tmp_path): ...
```

The valid test uploads bytes beginning with `b"PK\x03\x04"` as `demo.apk`; the unsafe filename test uses `../../escape.apk` and asserts no file appears outside the configured APK directory.

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd backend && python -m pytest tests/test_apks.py -v`
Expected: FAIL because upload routes/storage are missing.

- [ ] **Step 3: Implement minimal SQLite-backed storage and routes**

Storage behavior:

```text
<data_dir>/metadata.sqlite3
<data_dir>/apks/<uuid>.apk
```

SQLite table:

```sql
CREATE TABLE IF NOT EXISTS apks (
  id TEXT PRIMARY KEY,
  original_filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  storage_path TEXT NOT NULL
)
```

Route validation checks a case-insensitive `.apk` suffix, reads at most `max_apk_bytes + 1`, rejects oversized files, hashes with SHA-256, persists by generated UUID filename, and returns `APKRecord` without exposing `storage_path`.

- [ ] **Step 4: Run focused and full backend tests**

Run: `cd backend && python -m pytest tests/test_apks.py -v && python -m pytest -v`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add apk upload and storage api`

---

### Task 3: SwiftUI APK library shell

**Files:**
- Create: `ios/project.yml`
- Create: `ios/AndroidEmulator/App/AndroidEmulatorApp.swift`
- Create: `ios/AndroidEmulator/Models/APKItem.swift`
- Create: `ios/AndroidEmulator/Networking/APIClient.swift`
- Create: `ios/AndroidEmulator/ViewModels/LibraryViewModel.swift`
- Create: `ios/AndroidEmulator/Views/LibraryView.swift`
- Create: `ios/AndroidEmulator/Views/SettingsView.swift`
- Create: `ios/AndroidEmulator/Info.plist`
- Test: `ios/AndroidEmulatorTests/APIClientTests.swift`

**Interfaces:**
- `struct APKItem: Codable, Identifiable, Equatable`
- `final class APIClient` initialized with `baseURL: URL`.
- `func listAPKs() async throws -> [APKItem]`
- `func uploadAPK(fileURL: URL) async throws -> APKItem`
- `@MainActor final class LibraryViewModel: ObservableObject` exposes `items`, `isLoading`, `uploadProgressText`, `errorMessage`.

- [ ] **Step 1: Write model/network construction tests first**

Tests verify JSON decoding for an APK item and that `APIClient.endpoint("/v1/apks")` resolves relative to `https://example.test` as `https://example.test/v1/apks`.

- [ ] **Step 2: Run iOS tests and confirm RED**

Run on macOS: `cd ios && xcodegen generate && xcodebuild test -scheme AndroidEmulator -destination 'platform=iOS Simulator,name=iPhone 16' CODE_SIGNING_ALLOWED=NO`
Expected: FAIL because the Swift types do not exist.

- [ ] **Step 3: Implement minimal iOS shell**

Main UI requirements:

```text
Navigation title: Android Emulator
Toolbar: Settings
Primary button: Add APK
List: uploaded APK filename, size, created date
Empty state: No APKs yet
Upload state: visible ProgressView
Error state: visible message + Retry
```

`fileImporter` accepts `.data` and additionally verifies `url.pathExtension.lowercased() == "apk"` before upload. Security-scoped resource access is started/stopped around the upload. Backend URL defaults to `http://127.0.0.1:8000` and can be changed in Settings.

- [ ] **Step 4: Generate project and run tests/build**

Run:

```bash
cd ios
xcodegen generate
xcodebuild test -scheme AndroidEmulator -destination 'platform=iOS Simulator,name=iPhone 16' CODE_SIGNING_ALLOWED=NO
xcodebuild build -scheme AndroidEmulator -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' CODE_SIGNING_ALLOWED=NO
```

Expected: tests PASS and device build succeeds.

- [ ] **Step 5: Commit**

Commit message: `feat: add swiftui apk library client`

---

### Task 4: CI and downloadable IPA artifact

**Files:**
- Create: `.github/workflows/backend-ci.yml`
- Create: `.github/workflows/build-ios.yml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`

**Interfaces:**
- Workflow artifact name: `AndroidEmulator-unsigned-ipa`
- IPA filename: `AndroidEmulator-unsigned.ipa`

- [ ] **Step 1: Add backend CI**

Workflow runs on pull requests and pushes affecting `backend/**`, installs Python 3.12 and executes `python -m pytest -v` from `backend/`.

- [ ] **Step 2: Add iOS build workflow**

Workflow runs on `workflow_dispatch`, pull requests affecting `ios/**`, and pushes to `main`/`feat/**` affecting `ios/**` or the workflow itself.

Required build sequence:

```bash
brew install xcodegen
cd ios
xcodegen generate
xcodebuild build \
  -project AndroidEmulator.xcodeproj \
  -scheme AndroidEmulator \
  -configuration Release \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -derivedDataPath "$RUNNER_TEMP/DerivedData" \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO
APP_PATH=$(find "$RUNNER_TEMP/DerivedData/Build/Products/Release-iphoneos" -maxdepth 1 -name '*.app' -print -quit)
mkdir -p "$RUNNER_TEMP/ipa/Payload"
cp -R "$APP_PATH" "$RUNNER_TEMP/ipa/Payload/AndroidEmulator.app"
cd "$RUNNER_TEMP/ipa"
zip -qry "$GITHUB_WORKSPACE/AndroidEmulator-unsigned.ipa" Payload
```

Then upload with `actions/upload-artifact@v4` using artifact name `AndroidEmulator-unsigned-ipa`.

- [ ] **Step 3: Add repository hygiene and docs**

`.gitignore` excludes `.DS_Store`, `__pycache__`, `.pytest_cache`, `backend/data`, `ios/*.xcodeproj`, Xcode DerivedData and user state.

`.env.example` contains:

```dotenv
ANDROID_EMULATOR_DATA_DIR=./data
ANDROID_EMULATOR_MAX_APK_BYTES=536870912
```

README explains that the produced IPA is unsigned/re-signable and will not install until the user signs it with a valid certificate/profile or a compatible signing service/tool.

- [ ] **Step 4: Verify workflows syntactically and trigger CI**

Push branch and confirm GitHub Actions creates runs for backend tests and iOS build. If automatic path filters do not create the iOS run for the first commit, invoke `workflow_dispatch` manually.

Expected: backend CI green; iOS workflow green; artifact `AndroidEmulator-unsigned-ipa` contains `AndroidEmulator-unsigned.ipa`.

- [ ] **Step 5: Commit**

Commit message: `ci: add backend checks and unsigned ipa build`

---

## Self-review

- Spec coverage for Phase 1: repository structure, backend skeleton/tests, iOS shell, APK upload/list, CI, and IPA artifact are all mapped to tasks.
- Android runtime, ADB session lifecycle and WebRTC are intentionally deferred to Phases 2–3 per the approved design.
- No committed secrets are required.
- The unsigned IPA is explicitly documented as re-signable rather than install-ready.
- Public interfaces used across tasks have stable names and types.
