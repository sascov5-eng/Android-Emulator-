# Phase 2 Android Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a testable ReDroid/ADB runtime orchestration layer and REST API that can start, stop, reset, install, launch and inspect Android applications without exposing ADB publicly.

**Architecture:** `RuntimeService` owns state and orchestration. It depends on `RuntimeDriver` and `ADBClient` protocols; Docker CLI and subprocess ADB are concrete adapters. FastAPI receives injected service/adapters so CI uses fakes while production uses Docker/ReDroid.

**Tech Stack:** Python 3.12, FastAPI, dataclasses/protocols, subprocess, Docker CLI, Android platform-tools/ADB, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-31-phase2-runtime-design.md`

## Global Constraints

- ADB must never bind to `0.0.0.0`; default host is `127.0.0.1`.
- Existing Phase 1 API and six tests must remain compatible.
- Runtime API prefix is `/v1/runtime`.
- `stop` preserves Android data; `reset` destroys runtime data.
- Raw Docker/ADB stderr must not be returned to API clients.
- CI must run without Docker/ReDroid by injecting fake adapters.
- APK filesystem paths are resolved only through `APKStorage`.

---

### Task 1: Runtime domain model and service lifecycle

**Files:**
- Create: `backend/app/runtime/models.py`
- Create: `backend/app/runtime/interfaces.py`
- Create: `backend/app/runtime/service.py`
- Create: `backend/app/runtime/__init__.py`
- Test: `backend/tests/test_runtime_service.py`

**Interfaces:**
- Produces: `RuntimeState`, `RuntimeEndpoint`, `RuntimeStatus`, `AndroidApp`.
- Produces: `RuntimeDriver` and `ADBClient` protocols.
- Produces: `RuntimeService.start()`, `.status()`, `.stop()`, `.reset()`.

- [ ] **Step 1: Write lifecycle tests using fake runtime and fake ADB adapters**

Cover:

```python
def test_start_waits_for_boot_and_becomes_ready(): ...
def test_start_is_idempotent_when_ready(): ...
def test_boot_timeout_moves_service_to_error(): ...
def test_stop_is_idempotent(): ...
def test_reset_calls_driver_reset_and_waits_for_boot(): ...
```

The fake ADB raises `RuntimeBootTimeout` for timeout coverage.

- [ ] **Step 2: Run lifecycle tests and verify RED**

Run:

```bash
cd backend
python -m pytest tests/test_runtime_service.py -v
```

Expected: import/definition failures because runtime modules do not exist.

- [ ] **Step 3: Implement minimal domain/service code**

Use `RuntimeState(str, Enum)` with `stopped`, `starting`, `ready`, `stopping`, `error`.

`RuntimeService.start()`:

```python
self._status = RuntimeStatus(state=RuntimeState.STARTING)
endpoint = self._driver.start()
target = endpoint.adb_target
self._adb.wait_for_device(target, self._boot_timeout_seconds)
self._adb.wait_for_boot(target, self._boot_timeout_seconds)
self._endpoint = endpoint
self._status = RuntimeStatus(state=RuntimeState.READY, adb_target=target)
return self._status
```

Map adapter exceptions to domain exceptions without leaking stderr.

- [ ] **Step 4: Run lifecycle tests and full backend tests**

```bash
python -m pytest tests/test_runtime_service.py -v
python -m pytest -v
```

Expected: lifecycle tests pass and original six tests remain green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/runtime backend/tests/test_runtime_service.py
git commit -m "feat: add runtime lifecycle service"
```

---

### Task 2: APK lookup and Android install/launch application operations

**Files:**
- Modify: `backend/app/storage.py`
- Modify: `backend/app/runtime/service.py`
- Test: `backend/tests/test_runtime_apps.py`

**Interfaces:**
- Consumes: `APKStorage.get_apk(apk_id: str) -> APKRecord | None`.
- Produces: `APKStorage.path_for(apk_id: str) -> Path | None`.
- Produces: `RuntimeService.install(apk_id, storage) -> AndroidApp`.
- Produces: `RuntimeService.launch(apk_id, storage) -> AndroidApp`.
- Produces: `RuntimeService.list_apps() -> list[AndroidApp]`.

- [ ] **Step 1: Write failing application-operation tests**

Cover:

```python
def test_install_requires_ready_runtime(): ...
def test_install_rejects_unknown_apk(): ...
def test_install_uses_storage_path_and_returns_resolved_app(): ...
def test_launch_uses_resolved_package_and_activity(): ...
def test_list_apps_requires_ready_runtime(): ...
```

- [ ] **Step 2: Run tests and verify RED**

```bash
python -m pytest tests/test_runtime_apps.py -v
```

Expected: missing storage lookup/service methods.

- [ ] **Step 3: Implement storage lookup and service methods**

`APKStorage` must query its SQLite metadata database by ID and construct the canonical stored path from the record, never a client-provided path.

`install` performs:

```python
record = storage.get_apk(apk_id)
path = storage.path_for(apk_id)
self._adb.install(target, path)
app = self._adb.resolve_launchable(target, path)
self._installed[apk_id] = app
return app
```

`launch` resolves from `_installed` or `resolve_launchable`, then calls `ADBClient.launch`.

- [ ] **Step 4: Run focused and full tests**

```bash
python -m pytest tests/test_runtime_apps.py -v
python -m pytest -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/storage.py backend/app/runtime/service.py backend/tests/test_runtime_apps.py
git commit -m "feat: add runtime apk install and launch"
```

---

### Task 3: FastAPI runtime endpoints and stable error mapping

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_runtime_api.py`

**Interfaces:**
- Modify: `create_app(settings=None, runtime_service=None)` so tests inject a service.
- Produces routes:
  - `POST /v1/runtime/start`
  - `GET /v1/runtime/status`
  - `POST /v1/runtime/stop`
  - `POST /v1/runtime/reset`
  - `POST /v1/runtime/install/{apk_id}`
  - `POST /v1/runtime/launch/{apk_id}`
  - `GET /v1/runtime/apps`

- [ ] **Step 1: Write API tests**

Cover successful lifecycle responses and mappings for `RUNTIME_NOT_READY`, `APK_NOT_FOUND`, `APK_FILE_MISSING`, `RUNTIME_BOOT_TIMEOUT`, and adapter failures.

- [ ] **Step 2: Run API tests and verify RED**

```bash
python -m pytest tests/test_runtime_api.py -v
```

Expected: 404 routes / missing injection support.

- [ ] **Step 3: Implement routes and exception mapping**

Use response models from `runtime.models`. Keep `_error()` envelope unchanged.

Do not expose exception `.stderr`; use stable client messages.

- [ ] **Step 4: Run API and full backend suite**

```bash
python -m pytest tests/test_runtime_api.py -v
python -m pytest -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_runtime_api.py
git commit -m "feat: expose runtime api"
```

---

### Task 4: Subprocess ADB adapter

**Files:**
- Create: `backend/app/runtime/adb.py`
- Test: `backend/tests/test_adb_client.py`

**Interfaces:**
- Produces: `SubprocessADBClient` implementing `ADBClient`.
- Constructor consumes `adb_bin: str`, optional `aapt_bin: str | None`, and injectable runner for tests.

- [ ] **Step 1: Write command-construction tests**

Verify exact command shapes for:

```text
adb connect 127.0.0.1:5555
adb -s 127.0.0.1:5555 shell getprop sys.boot_completed
adb -s 127.0.0.1:5555 install -r <canonical path>
adb -s 127.0.0.1:5555 shell am start -n <package>/<activity>
adb -s 127.0.0.1:5555 shell monkey -p <package> 1
adb -s 127.0.0.1:5555 shell pm list packages -3
```

Also verify nonzero subprocess exit becomes `ADBCommandError` with sanitized public message.

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_adb_client.py -v
```

- [ ] **Step 3: Implement adapter**

Use `subprocess.run(..., capture_output=True, text=True, timeout=...)` through an injected runner. Poll boot completion until deadline with a short sleep; tests inject a no-op sleeper/clock if needed.

Parse `pm list packages -3` lines beginning with `package:`.

For launchable metadata, prefer `aapt dump badging <apk>` when configured and parse package plus `launchable-activity`; otherwise use installed package queries/fallback resolution.

- [ ] **Step 4: Run focused/full tests**

```bash
python -m pytest tests/test_adb_client.py -v
python -m pytest -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/runtime/adb.py backend/tests/test_adb_client.py
git commit -m "feat: add subprocess adb adapter"
```

---

### Task 5: Docker ReDroid runtime driver and secure configuration

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/runtime/docker_driver.py`
- Test: `backend/tests/test_runtime_config.py`
- Test: `backend/tests/test_docker_runtime.py`

**Interfaces:**
- Produces settings for runtime image/name/ADB host/port/boot timeout/binaries.
- Produces: `DockerRuntimeDriver` implementing `RuntimeDriver`.

- [ ] **Step 1: Write configuration and Docker command tests**

Verify:

```python
with pytest.raises(ValueError):
    Settings(adb_host="0.0.0.0")
```

Verify Docker start command contains:

```text
--privileged
--name android-emulator-redroid
-p 127.0.0.1:5555:5555
-v android-emulator-data:/data
```

and never contains `0.0.0.0:5555`.

Verify `stop` removes container but not volume; `reset` removes both and restarts.

- [ ] **Step 2: Run and verify RED**

```bash
python -m pytest tests/test_runtime_config.py tests/test_docker_runtime.py -v
```

- [ ] **Step 3: Implement settings and driver**

Use injected command runner. Driver methods use Docker CLI; sanitize failures into `RuntimeDriverError`.

- [ ] **Step 4: Run focused/full tests**

```bash
python -m pytest tests/test_runtime_config.py tests/test_docker_runtime.py -v
python -m pytest -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/runtime/docker_driver.py backend/tests/test_runtime_config.py backend/tests/test_docker_runtime.py
git commit -m "feat: add secure redroid docker driver"
```

---

### Task 6: Production dependency wiring

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/runtime/__init__.py`
- Test: `backend/tests/test_runtime_wiring.py`

**Interfaces:**
- Produces: `build_runtime_service(settings: Settings) -> RuntimeService`.
- `create_app()` builds production adapters only when no injected runtime service is provided.

- [ ] **Step 1: Write wiring tests**

Verify injected service is preserved and production settings construct Docker + subprocess adapters with expected configured values.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/test_runtime_wiring.py -v
```

- [ ] **Step 3: Implement wiring**

Construct `DockerRuntimeDriver` and `SubprocessADBClient` from `Settings`, then pass them to `RuntimeService`.

- [ ] **Step 4: Run full suite**

```bash
python -m pytest -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/runtime/__init__.py backend/tests/test_runtime_wiring.py
git commit -m "feat: wire production android runtime"
```

---

### Task 7: Linux deployment files and CI regression checks

**Files:**
- Create: `docker-compose.runtime.yml`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `.github/workflows/backend-ci.yml`

**Interfaces:**
- Compose/backend deployment exposes only HTTP backend port publicly.
- ReDroid ADB maps to `127.0.0.1` only.

- [ ] **Step 1: Add a CI static security assertion**

In backend CI, add a shell/Python check that rejects `0.0.0.0:5555` or a bare public `5555:5555` mapping in runtime compose/config files.

- [ ] **Step 2: Add deployment configuration**

Document Linux + Docker + privileged-container requirement. Include environment variables from the spec.

- [ ] **Step 3: Run local static checks where available and push**

Full authoritative verification is GitHub Actions.

- [ ] **Step 4: Verify GitHub Backend CI**

Expected: all tests and static ADB exposure check succeed.

- [ ] **Step 5: Verify iOS workflow still succeeds on Phase 2 commit**

No iOS runtime API UI is required in Phase 2, so existing IPA build must remain green.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.runtime.yml .env.example README.md .github/workflows/backend-ci.yml
git commit -m "docs: add redroid runtime deployment"
```

---

### Task 8: Final verification and review

**Files:** no new feature files unless findings require fixes.

- [ ] **Step 1: Run complete backend test suite in GitHub Actions**

Expected: zero failures.

- [ ] **Step 2: Verify latest iOS workflow**

Expected: metadata validation, unit tests, unsigned device build, IPA package verification, artifact upload all succeed.

- [ ] **Step 3: Compare Phase 2 branch against Phase 1 head**

Confirm changes are limited to Phase 2 runtime functionality, tests, deployment and docs.

- [ ] **Step 4: Review security invariants**

Confirm no `0.0.0.0:5555`, no iOS ADB code, no raw subprocess stderr in client error responses, and reset/stop persistence semantics are distinct.

- [ ] **Step 5: Open Phase 2 PR after Phase 1**

Base Phase 2 PR on `feat/phase1-foundation` while PR #1 is open, or retarget to `main` after PR #1 merges.
