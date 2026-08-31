# Phase 2 Android Runtime Design

## Goal

Add a server-side Android runtime layer that can create and destroy a ReDroid instance, wait until Android is booted, install APKs already stored by Phase 1, launch installed applications, list installed applications, and reset the runtime without exposing ADB directly to the iOS client or the public internet.

## Scope

Phase 2 includes:

- a runtime abstraction independent of Docker/ReDroid;
- a Docker-backed ReDroid runtime adapter;
- an ADB abstraction and subprocess-backed implementation;
- runtime lifecycle state and error mapping;
- API endpoints for start, status, stop, install, launch, reset and app listing;
- package/activity discovery from installed APKs;
- test fakes so CI does not require privileged Docker or Android;
- Docker Compose scaffolding for running the backend beside ReDroid on a Linux host;
- documentation for required Linux host capabilities and private ADB networking.

Phase 2 does not include:

- video/audio streaming;
- WebRTC;
- touch/gamepad input forwarding;
- multi-user authentication or quotas;
- Kubernetes orchestration;
- public ADB access;
- running Android locally on iOS.

Those belong to later phases.

## Architecture

The iOS app talks only to the FastAPI backend over HTTPS. The backend owns all Android lifecycle operations.

```text
iPhone / iPad
     |
     | HTTPS
     v
FastAPI
  |-- APKStorage
  |-- RuntimeService
        |-- RuntimeDriver --------> Docker / ReDroid
        |-- ADBClient ------------> private ADB endpoint
```

`RuntimeService` is the application-level orchestrator. It depends on protocol-style interfaces, not Docker or subprocess details. This keeps the API stable if ReDroid is replaced later.

## Runtime state model

The service exposes these states:

- `stopped`: no Android runtime exists;
- `starting`: runtime creation has begun but boot is not confirmed;
- `ready`: ADB is reachable and `sys.boot_completed` equals `1`;
- `stopping`: teardown is in progress;
- `error`: the latest lifecycle operation failed.

Status includes an optional error message and the private ADB target for diagnostics. The API must never return ADB credentials because no public ADB authentication scheme is part of this phase.

## Interfaces

### RuntimeDriver

```python
class RuntimeDriver(Protocol):
    def start(self) -> RuntimeEndpoint: ...
    def stop(self) -> None: ...
    def exists(self) -> bool: ...
    def reset(self) -> RuntimeEndpoint: ...
```

`RuntimeEndpoint` contains `adb_host` and `adb_port`. The Docker implementation publishes ADB only to loopback on the Linux host.

### ADBClient

```python
class ADBClient(Protocol):
    def wait_for_device(self, target: str, timeout_seconds: float) -> None: ...
    def wait_for_boot(self, target: str, timeout_seconds: float) -> None: ...
    def install(self, target: str, apk_path: Path) -> None: ...
    def resolve_launchable(self, target: str, apk_path: Path) -> AndroidApp: ...
    def launch(self, target: str, package_name: str, activity_name: str | None) -> None: ...
    def list_apps(self, target: str) -> list[AndroidApp]: ...
```

The concrete implementation executes `adb` and, for APK package metadata, `apkanalyzer` or `aapt` when available. If neither metadata tool is present, installation can still succeed, and package resolution falls back to querying the device package manager after install where possible.

## API

All runtime routes are under `/v1/runtime`.

### `POST /v1/runtime/start`

Starts ReDroid if not already running and waits until Android reports boot completion. Returns runtime status. Starting an already-ready runtime is idempotent.

### `GET /v1/runtime/status`

Returns the current state without mutating the runtime.

### `POST /v1/runtime/stop`

Stops and removes the runtime. Calling it when stopped remains successful and returns `stopped`.

### `POST /v1/runtime/reset`

Destroys the current runtime and its writable data volume, creates a clean runtime, and waits for boot completion.

### `POST /v1/runtime/install/{apk_id}`

Looks up the Phase 1 APK by ID, verifies the file still exists, requires a ready runtime, runs `adb install -r`, resolves package/activity metadata, and returns the installed app descriptor.

### `POST /v1/runtime/launch/{apk_id}`

Requires the APK to be installed/resolvable and launches its package. If a launchable activity is known it uses `am start`; otherwise it uses the package launch intent through `monkey` as a fallback.

### `GET /v1/runtime/apps`

Lists third-party packages known to Android, with package name and optional activity/label fields.

## Error model

Runtime errors use the same JSON envelope introduced in Phase 1:

```json
{
  "code": "RUNTIME_NOT_READY",
  "message": "Android runtime is not ready"
}
```

Stable codes in this phase:

- `RUNTIME_START_FAILED` -> 502;
- `RUNTIME_BOOT_TIMEOUT` -> 504;
- `RUNTIME_NOT_READY` -> 409;
- `RUNTIME_STOP_FAILED` -> 502;
- `RUNTIME_RESET_FAILED` -> 502;
- `ADB_COMMAND_FAILED` -> 502;
- `APK_NOT_FOUND` -> 404;
- `APK_FILE_MISSING` -> 410;
- `APP_RESOLUTION_FAILED` -> 422;
- `APP_LAUNCH_FAILED` -> 502.

Internal Docker/ADB stderr is logged server-side but must not be reflected verbatim to clients.

## Docker/ReDroid implementation

The production adapter uses Docker CLI commands rather than binding the Docker socket into the public backend container API. The Linux deployment places the backend in a trusted host context with Docker available. The runtime container is named deterministically, e.g. `android-emulator-redroid`.

Baseline runtime command semantics:

```text
docker run -d --rm --privileged \
  --name android-emulator-redroid \
  -p 127.0.0.1:<allocated_port>:5555 \
  -v android-emulator-data:/data \
  <configured redroid image>
```

The image name is configuration, not hard-coded business logic. Reset removes/recreates the writable data volume.

ADB is never bound to `0.0.0.0`.

## Configuration

Add these settings:

- `ANDROID_EMULATOR_RUNTIME_DRIVER=docker`;
- `ANDROID_EMULATOR_REDROID_IMAGE=redroid/redroid:15.0.0-latest` as a configurable default, overridable without code changes;
- `ANDROID_EMULATOR_RUNTIME_NAME=android-emulator-redroid`;
- `ANDROID_EMULATOR_ADB_HOST=127.0.0.1`;
- `ANDROID_EMULATOR_ADB_PORT=5555` or a host-selected port;
- `ANDROID_EMULATOR_BOOT_TIMEOUT_SECONDS=120`;
- `ANDROID_EMULATOR_ADB_BIN=adb`;
- optional `ANDROID_EMULATOR_AAPT_BIN=aapt`.

Configuration validation rejects non-positive ports/timeouts and a public ADB host such as `0.0.0.0` unless an explicit future unsafe-development override is introduced. No such override is included in Phase 2.

## Persistence

Phase 1 APK files and metadata remain in the backend data directory.

Runtime Android data uses a separate Docker volume. `stop` preserves it. `reset` deletes it. This distinction lets a user stop/start without losing app data while still providing an explicit clean-reset operation.

## Testing

CI must not require ReDroid. Tests inject `FakeRuntimeDriver` and `FakeADBClient` into `create_app`/`RuntimeService`.

Required tests cover:

- idempotent start;
- successful boot transition to `ready`;
- boot timeout mapping;
- idempotent stop;
- reset creates a clean endpoint;
- install refuses when runtime is not ready;
- install rejects unknown APK IDs;
- install resolves and returns package metadata;
- launch uses resolved package/activity;
- app listing requires ready runtime;
- Docker command construction binds ADB to loopback only;
- configuration rejects a public ADB host.

The existing six Phase 1 tests must continue to pass.

## Security constraints

1. iOS never speaks ADB.
2. ADB is bound only to loopback/private runtime networking.
3. Client responses never include raw subprocess stderr.
4. APK paths always come from `APKStorage`, never from user-controlled filesystem paths.
5. Runtime container name, image and ports are validated configuration values.
6. Docker/ReDroid operations stay behind the `RuntimeDriver` boundary.

## Success criteria

Phase 2 is complete when:

- all Phase 1 and Phase 2 backend tests pass in GitHub Actions;
- production Docker/ReDroid configuration is committed;
- API routes expose lifecycle/install/launch/list/reset behavior through injected adapters;
- ADB is never publicly exposed in generated deployment configuration;
- Phase 1 iOS IPA workflow still passes unchanged;
- the codebase is ready for Phase 3 streaming without changing the runtime API boundary.
