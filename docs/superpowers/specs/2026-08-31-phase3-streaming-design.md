# Phase 3 — Interactive Android Streaming Design

Date: 2026-08-31
Branch: `feat/phase3-streaming`
Base: `feat/phase2-runtime` at `76f1150556d8e7dda824220a868ac095fced62f1`

## Objective

Turn the existing cloud Android runtime into an interactive remote Android session on iPhone/iPad.

The Phase 3 success path is:

1. User uploads an APK from iOS.
2. Backend starts ReDroid and installs/launches the APK using the Phase 2 runtime API.
3. Backend starts a video capture process for that Android instance.
4. MediaMTX receives the video and exposes it as WebRTC/WHEP.
5. The iOS app opens an Android session screen and renders the live Android display.
6. Single-touch gestures and navigation buttons are sent back to the backend.
7. Backend maps normalized touch coordinates to Android display coordinates and injects the input through ADB.

Phase 3 does not add multi-user isolation, authentication, audio, multitouch, gamepad mapping, or production-grade TURN infrastructure. Those remain later hardening/feature phases.

## Architecture

```text
┌──────────────────────── iPhone / iPad ────────────────────────┐
│                                                               │
│  SwiftUI SessionView                                          │
│      │                                                        │
│      ├── WKWebView / WebRTC viewer                            │
│      │       │                                                │
│      │       └──── WHEP/WebRTC ───────────────────────────┐   │
│      │                                                    │   │
│      └── Gesture overlay                                  │   │
│              │                                            │   │
│              └──── WebSocket input ─────────────────┐     │   │
└─────────────────────────────────────────────────────┼─────┼───┘
                                                      │     │
                                                      ▼     ▼
┌──────────────────────── Linux host ────────────────────────────┐
│                                                               │
│ FastAPI                                                       │
│   ├── RuntimeService (Phase 2)                                │
│   ├── StreamManager                                           │
│   ├── Stream session API                                      │
│   └── Input WebSocket                                         │
│            │                                                  │
│            └── InputService ── ADB shell input                │
│                                                               │
│ ReDroid                                                       │
│    │                                                          │
│    ├── ADB on 127.0.0.1 only                                 │
│    └── screenrecord --output-format=h264 -                    │
│             │                                                 │
│             ▼                                                 │
│          FFmpeg                                               │
│             │ RTSP                                            │
│             ▼                                                 │
│          MediaMTX ───────────── WHEP/WebRTC ──────────────────┘
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## Chosen Transport

### Video source

The first Phase 3 implementation uses Android `screenrecord` through the already-private ADB channel:

```text
adb -s 127.0.0.1:5555 exec-out screenrecord \
  --output-format=h264 \
  --bit-rate <configured> \
  --size <configured width>x<configured height> \
  -
```

The capture process produces H.264 to stdout. The backend never forwards raw ADB to the client.

### Video publish path

FFmpeg consumes the H.264 stream and republishes it to a local MediaMTX RTSP path. MediaMTX then exposes the same path via WebRTC/WHEP.

The initial target is one stream path:

```text
android/session
```

The naming is intentionally abstracted behind `StreamManager` so later multi-session work can switch to per-session paths without changing iOS APIs.

### iOS playback

The iOS client embeds a `WKWebView` hosting a minimal local HTML/JavaScript WHEP player page. This keeps the first working WebRTC implementation independent of a native WebRTC binary dependency and allows the unsigned IPA pipeline to remain simple.

The web view has no arbitrary navigation surface. The only remote endpoint it receives is the backend-provided WHEP URL for the current session.

A future optimization may replace this with a native WebRTC renderer after the transport is proven.

## Stream Domain Model

### StreamState

```text
stopped
starting
live
error
```

### StreamStatus

Fields:

- `state`
- `session_id`
- `whep_url` when live
- `width`
- `height`
- `fps`

No internal command lines, process IDs, local ADB endpoints, stderr, or host filesystem paths are returned to clients.

### StreamManager responsibilities

`StreamManager` owns only media-process lifecycle:

- validate that Android runtime is `ready`;
- start MediaMTX if needed;
- launch capture/publish pipeline;
- wait for the stream to become readable;
- return stable public session metadata;
- stop capture processes idempotently;
- detect dead capture/publisher processes;
- transition to `error` on unexpected exit;
- sanitize process errors.

It does not install APKs or launch Android apps. Those remain in `RuntimeService`.

## Stream API

Initial REST API:

```text
GET  /v1/stream/status
POST /v1/stream/start
POST /v1/stream/stop
```

### POST /v1/stream/start

Precondition: runtime state is `ready`.

Response example:

```json
{
  "state": "live",
  "session_id": "default",
  "whep_url": "https://example.invalid/webrtc/android/session/whep",
  "width": 720,
  "height": 1280,
  "fps": 30
}
```

The backend constructs the public WHEP URL from an explicit configured public base URL. It never derives a trusted external address from the incoming `Host` header.

### Public errors

Stable client error envelope remains:

```json
{
  "code": "STREAM_START_FAILED",
  "message": "Android stream failed to start"
}
```

Expected codes include:

- `RUNTIME_NOT_READY` — 409
- `STREAM_START_FAILED` — 502
- `STREAM_NOT_AVAILABLE` — 503
- `STREAM_STOP_FAILED` — 502

Internal FFmpeg, ADB, MediaMTX, and subprocess stderr is not returned.

## Input Channel

### WebSocket

```text
WS /v1/stream/input
```

The socket is accepted only while runtime state is `ready` and a stream session is active/live.

Each message is JSON with a strict schema. Unknown event types or out-of-range values are rejected.

### Normalized pointer protocol

Coordinates are normalized to `[0.0, 1.0]` relative to the actual displayed Android video content, not the full iPhone screen.

Event shapes:

```json
{"type":"pointer_down","x":0.42,"y":0.61}
{"type":"pointer_move","x":0.43,"y":0.62}
{"type":"pointer_up","x":0.43,"y":0.62}
```

Navigation actions:

```json
{"type":"key","key":"back"}
{"type":"key","key":"home"}
{"type":"key","key":"recents"}
```

Supported keys are allow-listed. Arbitrary shell commands and arbitrary Android keycodes are not accepted from the client.

### Coordinate mapping

The backend maps normalized coordinates to configured/current Android display size:

```text
android_x = round(clamp(x, 0, 1) * (width - 1))
android_y = round(clamp(y, 0, 1) * (height - 1))
```

The iOS gesture surface first removes letterboxing/pillarboxing introduced by aspect-fit rendering. Gestures outside the actual video rectangle are ignored.

### Android injection

Phase 3 input uses the ADB shell `input` command family through a dedicated `InputAdapter`.

The adapter supports:

- tap/short click;
- key events for Back/Home/Recents;
- drag/swipe sequences;
- the closest available single-pointer `DOWN/MOVE/UP` injection supported by the host Android build.

`InputService` remains interface-driven so a later scrcpy control-protocol adapter can replace ADB input without changing the iOS message schema.

If the tested Android `input` implementation cannot preserve low-latency continuous pointer state reliably, Phase 3 will still ship tap/drag/key control and the continuous-pointer implementation will move behind a scrcpy control adapter in the next milestone. The public protocol remains unchanged.

## iOS Session UI

### Entry point

Each APK library item gains a `Run` action. The high-level flow is:

```text
Run APK
  ↓
ensure runtime ready
  ↓
install APK
  ↓
launch APK
  ↓
start stream
  ↓
open SessionView
```

Failures stop the sequence at the failing stage and show the backend's sanitized public error.

### SessionView

The new screen contains:

- full available Android video surface;
- connection state overlay (`Starting`, `Live`, `Disconnected`, `Error`);
- gesture capture overlay;
- bottom controls for Back, Home, Recents;
- fullscreen toggle;
- explicit close/stop-stream action.

The first version is portrait-first because ReDroid is currently configured for a phone-shaped display. The coordinate layer uses actual stream dimensions, so landscape support can be added without redesigning the protocol.

### Reconnect behavior

If the WebSocket disconnects, the client reconnects with bounded exponential backoff while the session screen remains open.

If video playback fails, the user sees a retry action. Automatic infinite retry loops are not allowed.

Closing `SessionView` closes the input WebSocket. The stream may be stopped explicitly on close for the single-user Phase 3 deployment.

## Deployment

### MediaMTX

Add a MediaMTX service to the runtime deployment configuration. Only ports required for the client-facing WebRTC/WHEP service are exposed. RTSP ingest remains private to the trusted host/container network.

MediaMTX configuration is committed to the repository and contains no credentials.

### Backend image

The runtime-controller image adds FFmpeg and any minimal networking/process utilities required for stream supervision.

The backend continues to have privileged infrastructure access because Phase 2 already mounts the Docker socket. This remains a trusted single-user deployment until the later hardening phase.

### Public URL configuration

New configuration includes an explicit public streaming base URL, for example:

```dotenv
ANDROID_EMULATOR_STREAM_PUBLIC_BASE_URL=https://android.example.com
```

The client-visible WHEP URL is created only from this configured value.

## Security Invariants

1. ADB remains loopback-only and is never returned to iOS.
2. RTSP ingest is private and not exposed as an internet-facing control surface.
3. The backend does not accept arbitrary shell commands through the input channel.
4. Input coordinates must be finite values in `[0,1]`.
5. Navigation keys are allow-listed.
6. Client responses contain no subprocess stderr, command lines, filesystem paths, or Docker identifiers.
7. The WebRTC public endpoint is derived from explicit trusted configuration, not request headers.
8. The web view does not become a general browser and only loads the generated player plus the configured stream endpoint.
9. No secrets are committed to the public repository.

## Testing Strategy

### Backend unit tests

Use fake process/runtime/input adapters to test:

- start requires ready runtime;
- stream start transitions `stopped → starting → live`;
- repeated start is idempotent;
- stop is idempotent;
- dead publisher transitions to `error`;
- public WHEP URL construction ignores request Host headers;
- subprocess errors are sanitized;
- pointer coordinate validation and mapping;
- unsupported keys/events are rejected;
- input is rejected when runtime/stream is not ready.

### Backend integration/config tests

CI validates:

- MediaMTX config parses/starts in a container;
- backend Docker image builds with FFmpeg available;
- deployment files do not expose ADB `5555` publicly;
- RTSP ingest is not bound as a public host port;
- configured WebRTC/WHEP port is intentional and documented.

GitHub-hosted CI cannot prove real ReDroid screen capture because privileged binder/kernel features are not guaranteed. That remains a deployment-host integration test.

### iOS tests

Add unit tests for:

- stream-status decoding;
- stream/input endpoint construction;
- normalized coordinate mapping with aspect-fit letterboxing;
- `Run` orchestration state transitions;
- navigation key message encoding.

The existing iOS GitHub Actions workflow must continue to:

- run simulator tests;
- perform unsigned arm64 device build;
- package the IPA;
- validate IPA metadata;
- upload the unsigned IPA artifact.

## Acceptance Criteria

Phase 3 code is acceptable when all of the following are true:

1. Backend exposes stream start/status/stop APIs with stable public errors.
2. Stream process lifecycle is interface-driven and tested without ReDroid in normal CI.
3. Deployment includes MediaMTX and FFmpeg-based H.264 publishing configuration.
4. ADB remains private and existing Phase 2 isolation checks continue to pass.
5. iOS provides a SessionView that can consume the configured WHEP/WebRTC stream.
6. iOS sends normalized single-pointer and navigation events over WebSocket.
7. Backend validates, maps, and injects those events through an `InputAdapter`.
8. Backend tests, deployment security checks, Docker build, iOS unit tests, device build, and IPA packaging all pass.
9. No authentication, audio, multitouch, gamepad, multi-user scheduling, or TURN-server work is silently included in this phase.

## Explicit Non-Goals

- local Android emulation on iPhone;
- Google Play Store/GMS integration;
- audio streaming;
- true multitouch;
- Bluetooth/gamepad translation;
- multi-user or concurrent Android sessions;
- production authentication/authorization;
- persistent public TURN infrastructure;
- App Store distribution approval;
- replacing ReDroid with another runtime.

## Follow-on

After this milestone, the highest-value next step is to benchmark latency and control quality on a real Linux/ReDroid host. If ADB input or `screenrecord` latency is insufficient for games, the next milestone replaces the media/control internals with a scrcpy-based low-latency adapter while preserving the Phase 3 public APIs and iOS interaction model.
