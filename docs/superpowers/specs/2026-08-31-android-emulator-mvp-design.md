# Android Emulator MVP — Design Specification

Date: 2026-08-31
Repository: `sascov5-eng/Android-Emulator-`

## Goal

Build an iOS application that lets a user upload an Android APK, start an isolated Android session in the cloud, install and launch the APK, view the Android screen on iPhone, and control it with touch input. The iOS project must be buildable entirely in GitHub Actions so the user can download an `.ipa` artifact without owning a PC.

## MVP success criteria

The MVP is considered successful when all of the following work end-to-end:

1. The iOS app can select an `.apk` file from Files.
2. The APK is uploaded to the backend.
3. The backend creates or attaches to an Android runtime session.
4. The APK is installed through ADB.
5. The package is launched automatically.
6. The Android display is streamed to the iOS app with acceptable interactive latency.
7. Touch input from the iPhone is translated into Android input events.
8. The user can stop the session.
9. GitHub Actions can produce a downloadable `.ipa` artifact from the repository.

## Architecture

```text
┌──────────────────────── iPhone ────────────────────────┐
│ SwiftUI app                                             │
│ - APK picker                                            │
│ - Library/session UI                                    │
│ - WebRTC player                                         │
│ - Touch/input capture                                   │
└───────────────────────┬────────────────────────────────┘
                        │ HTTPS / WebSocket / WebRTC
                        ▼
┌──────────────────── Backend API ────────────────────────┐
│ FastAPI                                                 │
│ - APK upload                                            │
│ - session lifecycle                                     │
│ - package install/launch                                │
│ - signaling                                             │
│ - auth/session token                                    │
└───────────────────────┬────────────────────────────────┘
                        │ ADB + runtime control
                        ▼
┌──────────────────── Android host ───────────────────────┐
│ Linux + Docker                                          │
│ - ReDroid container                                     │
│ - persistent user volume                                │
│ - ADB                                                   │
│ - display capture / WebRTC bridge                       │
└────────────────────────────────────────────────────────┘
```

## Components

### 1. iOS client

Technology: Swift 6 / SwiftUI.

Responsibilities:

- pick APK files using the native document picker;
- upload APK with progress indication;
- show upload/install/session state;
- list uploaded apps known to the backend;
- start and stop Android sessions;
- render the remote Android video stream;
- send touch events and orientation changes;
- show useful failure states rather than raw backend errors.

The first MVP does not require user registration UI. It will support a simple API token/configuration model so the runtime path can be proven before account management is added.

### 2. Backend

Technology: Python 3.12 + FastAPI.

Initial API surface:

- `GET /health`
- `POST /v1/apks` — upload APK
- `GET /v1/apks` — list uploaded APKs
- `POST /v1/sessions` — create Android session
- `GET /v1/sessions/{id}` — get session state
- `POST /v1/sessions/{id}/install` — install selected APK
- `POST /v1/sessions/{id}/launch` — launch installed package
- `POST /v1/sessions/{id}/stop` — stop session
- `POST /v1/sessions/{id}/input/touch` — fallback input endpoint
- `POST /v1/webrtc/offer` — WebRTC signaling entry point

Responsibilities:

- validate file type and upload size;
- store APK metadata;
- manage runtime/session identifiers;
- invoke ADB operations through a dedicated adapter layer;
- return normalized error codes to the iOS client;
- keep runtime-specific implementation out of route handlers.

### 3. Android runtime

Primary runtime: ReDroid in Docker on Linux.

Responsibilities:

- provide a bootable Android environment;
- expose ADB only to the backend/private network;
- mount persistent data volume when persistence is enabled;
- allow APK install, package discovery, app launch, and input injection;
- expose a display/audio source for the streaming bridge.

The runtime layer will be abstracted behind a backend interface so a managed provider can replace ReDroid later without rewriting the iOS app or public API.

### 4. Streaming

Primary transport: WebRTC.

Responsibilities:

- encode and deliver Android video to iPhone;
- deliver audio when supported by the runtime bridge;
- keep interaction latency low enough for ordinary apps and casual games;
- carry session signaling through the backend;
- reconnect cleanly when the network changes.

For the first milestone, video + touch is mandatory. Audio is included in the architecture but may follow immediately after the first verified interactive stream if the chosen capture bridge requires separate work.

## Data model

### APK

- `id`
- `original_filename`
- `sha256`
- `size_bytes`
- `package_name` when discovered
- `version_name` when discovered
- `created_at`
- `storage_path`

### Session

- `id`
- `status`: `starting | ready | installing | running | stopping | stopped | failed`
- `runtime_id`
- `apk_id`
- `package_name`
- `created_at`
- `updated_at`
- `error_code` / `error_message` when failed

## Storage

For the first deployment:

- APKs stored on backend-local persistent storage;
- metadata stored in SQLite for MVP;
- runtime data stored in Docker volumes.

The storage layer will be kept replaceable so object storage and PostgreSQL can be introduced later without changing the iOS API contract.

## Security boundaries

- APKs are treated as untrusted input.
- Android runtime must be isolated from the backend host as much as the selected hosting environment permits.
- ADB must never be publicly exposed to the internet.
- Backend accepts only authenticated API calls once deployed publicly.
- APK file names are never trusted as filesystem paths.
- File size limits and MIME/extension checks are enforced.
- Secrets are stored in environment variables / GitHub Actions Secrets, not committed to the repository.

## GitHub Actions / IPA build

Workflow target: `.github/workflows/build-ios.yml`.

Responsibilities:

- run on manual dispatch and selected branch pushes;
- use a GitHub-hosted macOS runner;
- select a supported Xcode version;
- resolve Swift dependencies;
- build and test the iOS project;
- archive the app;
- export an `.ipa` when signing material is configured;
- upload the resulting `.ipa` as a workflow artifact.

Signing material will not be stored in source control. The workflow will support GitHub Secrets for certificate/profile-based signing. If unsigned or ad-hoc packaging is technically viable for a given build path, it will remain a development-only option; the normal distribution path assumes the user provides valid signing credentials.

## Repository layout

```text
/
├── ios/
│   └── AndroidEmulator/
├── backend/
│   ├── app/
│   ├── tests/
│   └── Dockerfile
├── android-server/
│   ├── docker-compose.yml
│   ├── scripts/
│   └── README.md
├── streaming/
├── docs/
│   └── superpowers/specs/
├── .github/
│   └── workflows/
├── .env.example
└── README.md
```

## Error handling

The backend exposes stable machine-readable error codes such as:

- `APK_INVALID`
- `APK_TOO_LARGE`
- `RUNTIME_START_FAILED`
- `ADB_UNAVAILABLE`
- `APK_INSTALL_FAILED`
- `PACKAGE_NOT_FOUND`
- `APP_LAUNCH_FAILED`
- `STREAM_NEGOTIATION_FAILED`
- `SESSION_NOT_FOUND`

The iOS client maps these to user-facing messages and retry actions.

## Testing strategy

### Backend

- unit tests for storage, APK validation, session state transitions, and runtime adapter behavior;
- API tests with mocked runtime/ADB adapter;
- health check in CI.

### iOS

- unit tests for API models and state reducers/view models;
- UI smoke tests where practical on GitHub macOS runners;
- build verification on every relevant change.

### Runtime

- shell-level smoke test that verifies Android boot, ADB connection, APK install, package launch, and input injection;
- deployment README with exact verification commands.

## Delivery phases

### Phase 1 — repository foundation

- project structure;
- backend skeleton + tests;
- iOS shell app;
- CI for backend and iOS build;
- `.ipa` artifact pipeline foundation.

### Phase 2 — Android runtime integration

- ReDroid deployment files;
- ADB adapter;
- session create/start/stop;
- APK install and launch.

### Phase 3 — interactive streaming

- display capture;
- WebRTC signaling and stream;
- iOS player;
- touch mapping.

### Phase 4 — product hardening

- authentication;
- persistence controls;
- better error recovery;
- audio;
- gamepad mapping;
- multi-user isolation;
- production database/object storage if needed.

## Non-goals for the first MVP

- App Store distribution;
- running Android bytecode locally inside iOS;
- multiple simultaneous Android sessions per user;
- billing;
- social/account features;
- root-management UI;
- anti-cheat bypasses or DRM circumvention;
- guaranteed compatibility with every APK.

## Key implementation decision

The public API and iOS client must depend on a generic `AndroidRuntime` backend interface, not directly on ReDroid. ReDroid is the first runtime implementation, but this boundary prevents vendor/runtime lock-in and lets the project move to a managed Android provider later if server constraints make ReDroid unsuitable.
