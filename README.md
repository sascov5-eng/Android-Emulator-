# Android Emulator

An iOS client plus a cloud Android runtime controller. The iPhone app uploads APK files to a FastAPI backend. The backend can create a ReDroid Android container, connect to it through private ADB, install uploaded APKs, resolve their Android package/activity and launch them.

Interactive video/audio streaming to iOS is the next phase.

## Current status

### Phase 1 — complete

- SwiftUI iOS application for selecting and uploading `.apk` files;
- editable backend URL in the iOS app;
- APK library fetched from the backend;
- safe APK upload validation and UUID storage paths;
- SHA-256 metadata and SQLite index;
- automated backend/iOS tests;
- downloadable unsigned/re-signable `.ipa` from GitHub Actions.

### Phase 2 — runtime foundation

- runtime lifecycle model: `stopped`, `starting`, `ready`, `stopping`, `error`;
- ReDroid lifecycle behind a `RuntimeDriver` interface;
- Docker-backed production runtime driver;
- subprocess ADB adapter;
- private/loopback-only ADB binding;
- Android boot-completion polling;
- APK install through `adb install -r`;
- package/activity discovery with `aapt dump badging`;
- package launch through `am start` with `monkey` fallback;
- third-party package listing;
- `stop` preserves Android data;
- `reset` destroys the Android data volume and creates a clean runtime;
- stable HTTP error codes without leaking Docker/ADB stderr;
- fake runtime/ADB adapters for CI, so tests do not require privileged Android.

Not implemented yet:

- Android display/audio streaming;
- WebRTC signaling/player;
- touch/keyboard/gamepad input forwarding;
- authentication and multi-user isolation.

## Repository layout

```text
backend/                  FastAPI API, runtime controller and tests
ios/                      SwiftUI app and XcodeGen project definition
docker-compose.runtime.yml Linux runtime-controller deployment
.github/workflows/        Backend CI and iOS IPA build
docs/superpowers/specs/   Approved architecture
docs/superpowers/plans/   Implementation plans
```

## Backend API

APK endpoints:

```text
GET  /health
GET  /v1/apks
POST /v1/apks
```

Android runtime endpoints:

```text
GET  /v1/runtime/status
POST /v1/runtime/start
POST /v1/runtime/stop
POST /v1/runtime/reset
POST /v1/runtime/install/{apk_id}
POST /v1/runtime/launch/{apk_id}
GET  /v1/runtime/apps
```

`POST /v1/apks` accepts multipart form-data with a field named `file`. Only filenames ending in `.apk` are accepted. The maximum upload defaults to 512 MiB.

Uploaded files are stored with generated UUID filenames rather than user-supplied filesystem paths. Runtime install/launch resolves paths only through this storage index.

## Runtime behavior

`POST /v1/runtime/start` creates ReDroid when necessary, connects ADB and waits until Android reports:

```text
sys.boot_completed=1
```

Starting an already-ready runtime is idempotent.

`POST /v1/runtime/stop` removes the ReDroid container but keeps its named `/data` volume, so Android applications and data survive a later start.

`POST /v1/runtime/reset` removes the container **and** Android data volume, then creates a clean Android instance.

`POST /v1/runtime/install/{apk_id}` performs `adb install -r` against the canonical APK file stored by the backend and returns the resolved Android package/activity.

`POST /v1/runtime/launch/{apk_id}` launches the resolved activity. If an explicit launchable activity is unavailable, the ADB adapter falls back to the package launch intent through `monkey`.

## Environment variables

Copy `.env.example` to `.env` on the Linux server and adjust the image/version as required:

```dotenv
ANDROID_EMULATOR_DATA_DIR=./data
ANDROID_EMULATOR_MAX_APK_BYTES=536870912
ANDROID_EMULATOR_RUNTIME_DRIVER=docker
ANDROID_EMULATOR_REDROID_IMAGE=redroid/redroid:15.0.0-latest
ANDROID_EMULATOR_RUNTIME_NAME=android-emulator-redroid
ANDROID_EMULATOR_RUNTIME_VOLUME=android-emulator-data
ANDROID_EMULATOR_ADB_HOST=127.0.0.1
ANDROID_EMULATOR_ADB_PORT=5555
ANDROID_EMULATOR_BOOT_TIMEOUT_SECONDS=120
ANDROID_EMULATOR_ADB_BIN=adb
ANDROID_EMULATOR_AAPT_BIN=aapt
ANDROID_EMULATOR_DOCKER_BIN=docker
```

The application rejects non-loopback `ANDROID_EMULATOR_ADB_HOST` values. Do not change this to `0.0.0.0`.

## Linux runtime deployment

A real ReDroid session cannot run on GitHub itself. It needs a Linux host capable of privileged Docker containers.

Server requirements for Phase 2:

- Linux x86_64 or arm64 supported by the chosen ReDroid image;
- Docker Engine;
- permission to start privileged containers;
- `/var/run/docker.sock` available to the trusted runtime-controller container when using the supplied Compose file;
- sufficient CPU/RAM/storage for Android;
- firewall/reverse proxy exposing the backend API, **not ADB port 5555**.

The backend image contains the Docker CLI, `adb` and `aapt`. The supplied controller deployment uses host networking so the backend can reach ReDroid through host loopback while the runtime driver creates ReDroid dynamically.

```bash
cp .env.example .env
docker compose -f docker-compose.runtime.yml build
docker compose -f docker-compose.runtime.yml up -d
```

Then verify:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/v1/runtime/start
curl http://127.0.0.1:8000/v1/runtime/status
```

The ReDroid container created by the backend uses the equivalent of:

```text
--privileged
-p 127.0.0.1:5555:5555
-v android-emulator-data:/data
```

There is intentionally no public `5555:5555` mapping.

### Docker socket warning

`docker-compose.runtime.yml` mounts `/var/run/docker.sock` into the backend because the Runtime Manager controls ReDroid through the host Docker daemon. Access to that socket is effectively host-level Docker control. Treat the backend as privileged infrastructure: do not expose an unauthenticated deployment to arbitrary users. Authentication, quotas and per-user runtime isolation are Phase 4 work and are required before a public multi-user service.

## Run backend directly on Linux

For development or a host-native deployment, install Python 3.12+, Docker, ADB and AAPT, then:

```bash
cd backend
python -m pip install -e '.[test]'
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Tests:

```bash
cd backend
python -m pytest -v
```

## iOS app

The project is defined in `ios/project.yml` and generated with XcodeGen. The Phase 1 interface currently provides:

- **Add APK** file picker;
- uploaded APK library;
- upload/loading/error states;
- pull-to-refresh;
- **Settings** screen for the backend URL.

The development default backend URL is `http://127.0.0.1:8000`. On a physical iPhone this must be changed to the HTTPS/public address of the backend server.

The runtime API exists server-side in Phase 2. The full-screen Android streaming/player UI is Phase 3.

## Get the IPA without a PC

Open the repository's **Actions** tab and run/open **Build iOS IPA**. A successful run uploads:

```text
AndroidEmulator-unsigned-ipa
```

Inside it is:

```text
AndroidEmulator-unsigned.ipa
```

The IPA is an unsigned arm64 iPhone device build intended for later re-signing. No Apple signing key, certificate, provisioning profile or account credential is committed to this repository.

## Security invariants

- iOS never connects to ADB directly.
- ADB host is loopback-only.
- The runtime Docker port mapping binds port 5555 to loopback only.
- Docker/ADB stderr is not returned verbatim to API clients.
- Client-controlled APK filenames are never used as install filesystem paths.
- `stop` and `reset` have deliberately different persistence semantics.
- A production public service still needs authentication and per-user isolation before untrusted users are allowed to control runtimes.

## Roadmap

### Phase 3 — interactive streaming

- capture Android display and audio;
- WebRTC signaling/media transport;
- iOS player;
- touch coordinate mapping;
- keyboard and gamepad input forwarding;
- reconnect/session recovery.

### Phase 4 — hardening and multi-user operation

- authentication;
- authorization and quotas;
- per-user Android instance isolation;
- persistent session ownership;
- production object/database storage;
- rate limiting/auditing;
- production HTTPS/ATS hardening.

## Design documents

- `docs/superpowers/specs/2026-08-31-android-emulator-mvp-design.md`
- `docs/superpowers/plans/2026-08-31-phase1-foundation.md`
- `docs/superpowers/specs/2026-08-31-phase2-runtime-design.md`
- `docs/superpowers/plans/2026-08-31-phase2-runtime.md`
