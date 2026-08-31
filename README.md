# Android Emulator

An iOS client plus a cloud Android runtime controller. The iPhone app uploads APK files to a FastAPI backend. The backend creates a ReDroid Android container, installs/launches APKs through private ADB, captures the Android display, publishes it through MediaMTX/WebRTC, and receives normalized touch/navigation input from iOS.

## Current status

### Phase 1 — iOS/APK foundation

- SwiftUI APK picker, upload and library;
- editable backend URL;
- safe UUID-backed APK storage with SHA-256 metadata and SQLite index;
- unsigned/re-signable arm64 IPA produced by GitHub Actions.

### Phase 2 — Android runtime

- ReDroid lifecycle: start/status/stop/reset;
- Docker-backed runtime driver;
- loopback-only ADB;
- Android boot polling;
- `adb install -r`;
- package/activity discovery with `aapt dump badging`;
- app launch with `am start` and `monkey` fallback;
- persistent `stop` and destructive clean `reset` semantics;
- stable sanitized API errors.

### Phase 3 — interactive streaming

- Android H.264 capture through private ADB `screenrecord`;
- FFmpeg publisher to private RTSP ingest;
- MediaMTX WHEP/WebRTC playback;
- iOS full-screen `SessionView` with Run action from the APK library;
- aspect-fit touch coordinate mapping;
- WebSocket pointer input and Back/Home/Recents navigation;
- bounded reconnect behavior for WebRTC and input WebSocket;
- automatic capture restart after the Android `screenrecord` segment limit;
- Phase 3 IPA version `0.3.0` / build `3`.

Phase 3 remains a single-user MVP. Audio, true multitouch, gamepad translation, authentication, multi-user scheduling and production TURN infrastructure are not included yet.

## Repository layout

```text
backend/                    FastAPI API, runtime/stream/input controller and tests
ios/                        SwiftUI app and XcodeGen project
streaming/                  MediaMTX configuration
docker-compose.runtime.yml  Linux runtime deployment
.github/workflows/          Backend CI and iOS IPA build
docs/superpowers/specs/     Approved designs
docs/superpowers/plans/     Implementation plans
```

## API

APK endpoints:

```text
GET  /health
GET  /v1/apks
POST /v1/apks
```

Runtime endpoints:

```text
GET  /v1/runtime/status
POST /v1/runtime/start
POST /v1/runtime/stop
POST /v1/runtime/reset
POST /v1/runtime/install/{apk_id}
POST /v1/runtime/launch/{apk_id}
GET  /v1/runtime/apps
```

Streaming endpoints:

```text
GET  /v1/stream/status
POST /v1/stream/start
POST /v1/stream/stop
WS   /v1/stream/input
```

The input WebSocket accepts only strict normalized events:

```json
{"type":"pointer_down","x":0.42,"y":0.61}
{"type":"pointer_move","x":0.45,"y":0.63}
{"type":"pointer_up","x":0.45,"y":0.63}
{"type":"key","key":"back"}
```

Allowed navigation keys are only `back`, `home`, and `recents`. Arbitrary shell commands and arbitrary Android keycodes are not accepted.

## Phase 3 media path

```text
ReDroid
  ↓ private ADB
screenrecord H.264
  ↓ stdout
FFmpeg
  ↓ private RTSP (127.0.0.1:8554)
MediaMTX
  ↓ WHEP/WebRTC
 iPhone / iPad
```

The capture segment is capped at 175 seconds because Android `screenrecord` has a hard duration limit. The backend detects an ended live capture and rebuilds the capture/publish pipeline. The iOS client polls stream health and the WHEP player has bounded reconnect logic.

## Environment

Copy `.env.example` to `.env` on the Linux host. Important values include:

```dotenv
ANDROID_EMULATOR_REDROID_IMAGE=redroid/redroid:15.0.0-latest
ANDROID_EMULATOR_ADB_HOST=127.0.0.1
ANDROID_EMULATOR_ADB_PORT=5555
ANDROID_EMULATOR_STREAM_PUBLIC_BASE_URL=https://android.example.com
ANDROID_EMULATOR_STREAM_WHEP_PATH=/android/session/whep
ANDROID_EMULATOR_STREAM_RTSP_URL=rtsp://127.0.0.1:8554/android/session
ANDROID_EMULATOR_STREAM_WIDTH=720
ANDROID_EMULATOR_STREAM_HEIGHT=1280
ANDROID_EMULATOR_STREAM_FPS=30
ANDROID_EMULATOR_STREAM_BITRATE=4000000
ANDROID_EMULATOR_STREAM_CAPTURE_SECONDS=175
```

`ANDROID_EMULATOR_STREAM_PUBLIC_BASE_URL` must be the URL the iPhone can reach for MediaMTX/WHEP. The backend does not trust the incoming HTTP `Host` header to construct this address.

## Linux deployment

A real Android session requires a Linux host capable of privileged ReDroid containers. GitHub Actions builds/tests the project but is not a persistent Android server.

Requirements:

- Linux host with Docker Engine;
- required ReDroid binder/kernel support;
- permission to start privileged containers;
- enough CPU/RAM/storage for Android;
- host/reverse-proxy networking that exposes the backend and intended WebRTC endpoints;
- **do not expose ADB 5555 or RTSP ingest 8554 publicly**.

Start the supplied deployment:

```bash
cp .env.example .env
docker compose -f docker-compose.runtime.yml build
docker compose -f docker-compose.runtime.yml up -d
```

The backend controller mounts `/var/run/docker.sock` because it creates and destroys the ReDroid container. Treat it as privileged infrastructure and do not expose an unauthenticated deployment to arbitrary users.

## iOS flow

```text
Add APK
  ↓
Run
  ↓
start Android runtime
  ↓
install APK
  ↓
launch APK
  ↓
start stream
  ↓
SessionView
  ↓
WebRTC video + touch/navigation input
```

The development backend URL defaults to `http://127.0.0.1:8000`. On a physical iPhone, change it in Settings to a backend address the phone can actually reach.

## Get the IPA without a PC

The `Build iOS IPA` workflow runs simulator tests, performs an unsigned arm64 device build, validates app metadata, packages the app and uploads an artifact named:

```text
AndroidEmulator-0.3.0-unsigned-ipa
```

Inside it is:

```text
AndroidEmulator-unsigned.ipa
```

The IPA is intentionally unsigned for later re-signing. No Apple certificate, provisioning profile, private key or Apple account credential is committed to this repository.

## Security invariants

- iOS never connects to ADB directly.
- ADB remains loopback-only.
- RTSP ingest remains loopback-only.
- subprocess stderr is not returned verbatim to clients.
- uploaded filenames are never used as trusted install filesystem paths.
- WebSocket input has a strict schema and allow-listed keys.
- WHEP public URL comes from explicit configuration.
- the WKWebView player loads generated local HTML and blocks ordinary external navigation.
- no secrets are committed to the public repository.

## Current limitations

- one Android session/user;
- no audio streaming;
- no true simultaneous multitouch;
- drag control is currently translated through ADB swipe semantics rather than scrcpy's lower-latency control protocol;
- no gamepad mapping;
- no authentication/authorization yet;
- no production TURN service;
- real end-to-end latency and compatibility still require testing on an actual ReDroid-capable Linux host.

The next performance milestone is to benchmark Phase 3 on a real host. If ADB input or `screenrecord` latency is insufficient for games, the media/control internals can be replaced with a scrcpy-based adapter while preserving the public API and iOS interaction model.

## Design documents

- `docs/superpowers/specs/2026-08-31-android-emulator-mvp-design.md`
- `docs/superpowers/plans/2026-08-31-phase1-foundation.md`
- `docs/superpowers/specs/2026-08-31-phase2-runtime-design.md`
- `docs/superpowers/plans/2026-08-31-phase2-runtime.md`
- `docs/superpowers/specs/2026-08-31-phase3-streaming-design.md`
- `docs/superpowers/plans/2026-08-31-phase3-streaming.md`
