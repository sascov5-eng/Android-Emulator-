# Phase 3 Interactive Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single-user interactive Android session: H.264 screen capture from ReDroid, MediaMTX WebRTC/WHEP playback on iOS, and normalized single-pointer/navigation input sent back to Android.

**Architecture:** Phase 2 remains the runtime owner. A new `stream` package owns media lifecycle and input validation/injection behind interfaces. Media is captured with `adb exec-out screenrecord`, piped through FFmpeg to private RTSP ingest, and exposed by MediaMTX as WHEP/WebRTC. iOS uses a constrained `WKWebView` WHEP player plus a Swift gesture overlay and WebSocket input channel.

**Tech Stack:** Python 3.12, FastAPI, WebSocket, subprocess adapters, ReDroid/ADB, FFmpeg, MediaMTX, Swift 6, SwiftUI, WebKit, URLSessionWebSocketTask, XcodeGen, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-31-phase3-streaming-design.md`

## Global Constraints

- ADB must remain loopback-only and must never be returned to iOS.
- RTSP ingest must remain private; only intentional WebRTC/WHEP ports may be public.
- No arbitrary shell commands or arbitrary Android keycodes from the client.
- Input coordinates are finite normalized values in `[0, 1]`.
- Navigation keys are restricted to `back`, `home`, and `recents`.
- No audio, true multitouch, gamepad, authentication, multi-user scheduling, or TURN work in Phase 3.
- iOS deployment target remains 17.0 and unsigned arm64 IPA packaging must keep working.
- `screenrecord` capture segments use a 175-second limit and are rotated by the stream supervisor.

---

### Task 1: Stream domain and lifecycle service

**Files:**
- Create: `backend/app/stream/models.py`
- Create: `backend/app/stream/errors.py`
- Create: `backend/app/stream/interfaces.py`
- Create: `backend/app/stream/service.py`
- Create: `backend/app/stream/__init__.py`
- Test: `backend/tests/test_stream_service.py`

**Interfaces:**
- Consumes: Phase 2 runtime object exposing `status()` and returning a status whose `.state.value` is `ready` when usable.
- Produces: `StreamState`, `StreamStatus`, `StreamManager.start()`, `status()`, `stop()` and `StreamProcessAdapter` protocol.

- [ ] **Step 1: Write failing lifecycle tests** for ready-runtime precondition, stopped→starting→live transition, idempotent start/stop, dead publisher→error, and sanitized adapter failure.
- [ ] **Step 2: Run** `cd backend && python -m pytest tests/test_stream_service.py -v` and verify RED because `app.stream` does not exist.
- [ ] **Step 3: Implement minimal domain/service**. `StreamStatus` fields: `state`, `session_id`, `whep_url`, `width`, `height`, `fps`. `StreamManager` gets a runtime, process adapter, public WHEP URL, configured dimensions/fps; it never exposes adapter stderr.
- [ ] **Step 4: Run the focused tests** and verify GREEN.
- [ ] **Step 5: Commit** `feat: add stream lifecycle service`.

### Task 2: Stream settings and process adapter

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/stream/process.py`
- Test: `backend/tests/test_stream_config.py`
- Test: `backend/tests/test_stream_process.py`

**Interfaces:**
- Consumes: existing `Settings.adb_bin`, `adb_host`, `adb_port`.
- Produces: validated stream settings and `FFmpegScreenrecordAdapter.start_capture()/stop_capture()/is_alive()`.

- [ ] **Step 1: Write failing config tests** for non-empty explicit public base URL, private RTSP URL, positive width/height/fps/bitrate, capture limit `1..175`, and non-empty `ffmpeg_bin`.
- [ ] **Step 2: Write failing process-command tests** asserting `adb -s <loopback>:<port> exec-out screenrecord --output-format=h264 --bit-rate ... --size ... --time-limit 175 -` is piped into FFmpeg and that no shell interpolation is used.
- [ ] **Step 3: Run focused tests** and verify RED.
- [ ] **Step 4: Implement settings and process adapter** with `subprocess.Popen(list[str], shell=False)`, sanitized public exceptions, and process-group cleanup.
- [ ] **Step 5: Run focused tests** and verify GREEN.
- [ ] **Step 6: Commit** `feat: add screen capture process adapter`.

### Task 3: Stream REST API and production wiring

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/stream/__init__.py`
- Test: `backend/tests/test_stream_api.py`
- Test: `backend/tests/test_stream_wiring.py`

**Interfaces:**
- Consumes: `StreamManager` from Task 1, production adapter from Task 2.
- Produces: `GET /v1/stream/status`, `POST /v1/stream/start`, `POST /v1/stream/stop` with stable error envelopes.

- [ ] **Step 1: Write failing endpoint tests** for live response metadata, runtime-not-ready 409, stream-start-failed 502, unavailable 503, and sanitized messages.
- [ ] **Step 2: Run tests** and verify RED because stream injection/routes are absent.
- [ ] **Step 3: Add `stream_service` injection to `create_app()`**, register routes, and map stream exceptions to public codes without subprocess details.
- [ ] **Step 4: Add `build_stream_service(settings, runtime)`** production factory.
- [ ] **Step 5: Run full backend suite** `cd backend && python -m pytest -v` and verify GREEN.
- [ ] **Step 6: Commit** `feat: expose stream session API`.

### Task 4: Input protocol and ADB injection

**Files:**
- Create: `backend/app/stream/input.py`
- Test: `backend/tests/test_stream_input.py`

**Interfaces:**
- Produces: `InputEvent` parsing/validation, `map_point(x,y,width,height)`, `ADBInputAdapter`, and `InputService.handle(event)`.

- [ ] **Step 1: Write failing tests** for finite `[0,1]` coordinates, mapping formula, allow-listed keys, unknown events rejected, tap/drag/key command generation, and no stderr leakage.
- [ ] **Step 2: Run focused tests** and verify RED.
- [ ] **Step 3: Implement strict parser and mapper**. `pointer_down/move/up` are accepted by the public protocol; the ADB MVP may coalesce a completed pointer sequence into tap or swipe when continuous motion-event support is not reliable.
- [ ] **Step 4: Implement `ADBInputAdapter`** using argument arrays only; keys map to Android BACK/HOME/APP_SWITCH keyevents.
- [ ] **Step 5: Run tests** and verify GREEN.
- [ ] **Step 6: Commit** `feat: add normalized Android input service`.

### Task 5: Input WebSocket endpoint

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_stream_websocket.py`

**Interfaces:**
- Consumes: `StreamManager.status()`, runtime status, and `InputService.handle()`.
- Produces: `WS /v1/stream/input`.

- [ ] **Step 1: Write failing WebSocket tests** for rejection when runtime/stream is not live, valid pointer/key messages, invalid JSON/schema closure/error response, and unsupported keys.
- [ ] **Step 2: Run tests** and verify RED.
- [ ] **Step 3: Register WebSocket route** and inject `input_service` into `create_app()` for tests. Do not accept shell text or raw keycodes.
- [ ] **Step 4: Run full backend suite** and verify GREEN.
- [ ] **Step 5: Commit** `feat: add stream input websocket`.

### Task 6: MediaMTX and deployment

**Files:**
- Create: `streaming/mediamtx.yml`
- Modify: `docker-compose.runtime.yml`
- Modify: `backend/Dockerfile`
- Modify: `.env.example`
- Modify: `.github/workflows/backend-ci.yml`
- Modify: `README.md`

**Interfaces:**
- Produces: private RTSP ingest target and public WHEP/WebRTC service matching backend configuration.

- [ ] **Step 1: Add MediaMTX config** with RTSP bound only to the private/container interface and WebRTC HTTP endpoint explicitly exposed for clients.
- [ ] **Step 2: Add MediaMTX service to runtime compose** and add FFmpeg to backend image.
- [ ] **Step 3: Add env variables** for stream public base URL, WHEP path, RTSP publish URL, width, height, fps, bitrate, capture seconds, and FFmpeg binary.
- [ ] **Step 4: Extend CI security checks** to fail on public ADB `5555` or public RTSP `8554`, then build backend image and start/validate MediaMTX config container.
- [ ] **Step 5: Run GitHub backend CI** and verify tests + Docker image + MediaMTX validation all succeed.
- [ ] **Step 6: Commit** `infra: add MediaMTX streaming deployment`.

### Task 7: iOS stream models and API client

**Files:**
- Create: `ios/AndroidEmulator/Models/StreamStatus.swift`
- Create: `ios/AndroidEmulator/Models/RuntimeModels.swift`
- Modify: `ios/AndroidEmulator/Networking/APIClient.swift`
- Test: `ios/AndroidEmulatorTests/StreamingAPITests.swift`

**Interfaces:**
- Produces: async client methods `runtimeStart()`, `install(apkID:)`, `launch(apkID:)`, `streamStart()`, `streamStop()`, `streamStatus()`, and `inputWebSocketURL()`.

- [ ] **Step 1: Write failing Swift tests** for JSON decoding and endpoint construction including ws/wss conversion.
- [ ] **Step 2: Push RED revision and verify iOS Actions fails for missing types/methods.**
- [ ] **Step 3: Implement models/client methods** using existing decode/error conventions.
- [ ] **Step 4: Verify iOS unit tests GREEN in Actions.**
- [ ] **Step 5: Commit** `feat: add iOS streaming API client`.

### Task 8: iOS run orchestration

**Files:**
- Create: `ios/AndroidEmulator/ViewModels/SessionViewModel.swift`
- Modify: `ios/AndroidEmulator/ViewModels/LibraryViewModel.swift`
- Test: `ios/AndroidEmulatorTests/SessionViewModelTests.swift`

**Interfaces:**
- Produces: run sequence `runtimeStart → install → launch → streamStart`, published connection state, and close/stop behavior.

- [ ] **Step 1: Write failing tests** with an injected protocol/fake client covering successful sequence and stop-at-first-failure behavior.
- [ ] **Step 2: Verify RED in iOS Actions.**
- [ ] **Step 3: Implement testable session client protocol and `SessionViewModel`.**
- [ ] **Step 4: Verify GREEN in iOS Actions.**
- [ ] **Step 5: Commit** `feat: orchestrate Android sessions on iOS`.

### Task 9: WHEP player, aspect-fit mapping, and WebSocket input

**Files:**
- Create: `ios/AndroidEmulator/Streaming/WHEPWebView.swift`
- Create: `ios/AndroidEmulator/Streaming/InputSocket.swift`
- Create: `ios/AndroidEmulator/Streaming/VideoGeometry.swift`
- Test: `ios/AndroidEmulatorTests/VideoGeometryTests.swift`
- Test: `ios/AndroidEmulatorTests/InputEncodingTests.swift`

**Interfaces:**
- Produces: constrained player view, normalized content-coordinate mapping, and JSON WebSocket pointer/key sender.

- [ ] **Step 1: Write failing geometry tests** for portrait and landscape aspect-fit letterbox/pillarbox mapping and ignoring touches outside video content.
- [ ] **Step 2: Write failing message encoding tests** for pointer and navigation JSON.
- [ ] **Step 3: Implement `VideoGeometry` and `InputSocket`** with bounded reconnect behavior.
- [ ] **Step 4: Implement WHEP player web view** with local generated HTML/JS, disabled arbitrary navigation, inline autoplay, and only the supplied WHEP endpoint.
- [ ] **Step 5: Verify iOS unit tests GREEN.**
- [ ] **Step 6: Commit** `feat: add iOS WebRTC player and input transport`.

### Task 10: SessionView and library Run action

**Files:**
- Create: `ios/AndroidEmulator/Views/SessionView.swift`
- Modify: `ios/AndroidEmulator/Views/LibraryView.swift`
- Modify: `ios/AndroidEmulator/App/AndroidEmulatorApp.swift` only if routing requires it.

**Interfaces:**
- Consumes: SessionViewModel, WHEPWebView, InputSocket, VideoGeometry.
- Produces: end-user flow from APK row `Run` to interactive Android session.

- [ ] **Step 1: Add `Run` action** to each APK row and present/navigation-route to `SessionView` with selected APK and current backend URL.
- [ ] **Step 2: Implement SessionView** with video, connection overlay, gesture surface, Back/Home/Recents, fullscreen toggle, retry, and close.
- [ ] **Step 3: Map gestures only inside actual aspect-fit video rectangle** and emit normalized pointer events.
- [ ] **Step 4: Ensure closing session closes WebSocket and stops stream explicitly for Phase 3 single-user mode.**
- [ ] **Step 5: Run iOS simulator tests and device build through Actions.**
- [ ] **Step 6: Commit** `feat: add interactive Android session UI`.

### Task 11: Final CI, IPA, documentation, and PR

**Files:**
- Modify: `.github/workflows/build-ios.yml` only if additional WebKit/metadata checks are needed.
- Modify: `README.md`

**Interfaces:**
- Produces: verified unsigned Phase 3 IPA artifact and stacked PR against `feat/phase2-runtime`.

- [ ] **Step 1: Run latest backend CI** and require all tests, deployment isolation, backend Docker build, and MediaMTX config validation to succeed.
- [ ] **Step 2: Run latest iOS CI** and require unit tests, unsigned arm64 device build, IPA packaging, metadata validation, and artifact upload to succeed.
- [ ] **Step 3: Download the IPA artifact** and inspect `Payload/AndroidEmulator.app/Info.plist`, executable architecture, and absence of embedded signing material.
- [ ] **Step 4: Update README** with Phase 3 API, deployment, current limitations (single user, no audio/multitouch, screenrecord rotation), and how to obtain the unsigned IPA.
- [ ] **Step 5: Compare Phase 2 head to Phase 3 head** and verify changes are scoped to streaming/input/iOS session/deployment/docs.
- [ ] **Step 6: Open stacked PR** `feat/phase3-streaming` → `feat/phase2-runtime` with verification evidence.
