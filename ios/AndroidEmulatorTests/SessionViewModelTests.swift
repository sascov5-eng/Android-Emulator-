import XCTest
@testable import AndroidEmulator

@MainActor
final class SessionViewModelTests: XCTestCase {
    final class FakeAPI: SessionAPI, @unchecked Sendable {
        var calls: [String] = []
        var failAt: String?
        var statusState: StreamState = .live

        func runtimeStart() async throws -> RuntimeStatus {
            calls.append("runtimeStart")
            if failAt == "runtimeStart" { throw TestError.failed }
            return RuntimeStatus(state: .ready, adbTarget: "127.0.0.1:5555", error: nil)
        }

        func install(apkID: String) async throws -> AndroidApp {
            calls.append("install:\(apkID)")
            if failAt == "install" { throw TestError.failed }
            return AndroidApp(packageName: "com.example.demo", activityName: ".MainActivity", label: "Demo")
        }

        func launch(apkID: String) async throws -> AndroidApp {
            calls.append("launch:\(apkID)")
            if failAt == "launch" { throw TestError.failed }
            return AndroidApp(packageName: "com.example.demo", activityName: ".MainActivity", label: "Demo")
        }

        func streamStart() async throws -> StreamStatus {
            calls.append("streamStart")
            if failAt == "streamStart" { throw TestError.failed }
            return makeStreamStatus(state: .live)
        }

        func streamStatus() async throws -> StreamStatus {
            calls.append("streamStatus")
            if failAt == "streamStatus" { throw TestError.failed }
            return makeStreamStatus(state: statusState)
        }

        func streamStop() async throws -> StreamStatus {
            calls.append("streamStop")
            return makeStreamStatus(state: .stopped)
        }

        func inputWebSocketURL() -> URL? {
            URL(string: "wss://api.example.test/v1/stream/input")
        }

        private func makeStreamStatus(state: StreamState) -> StreamStatus {
            StreamStatus(
                state: state,
                sessionID: "default",
                whepURL: state == .live ? URL(string: "https://media.example.test/android/session/whep") : nil,
                width: 720,
                height: 1280,
                fps: 30,
                error: state == .error ? "stream error" : nil
            )
        }
    }

    enum TestError: Error { case failed }

    func testStartRunsRuntimeInstallLaunchAndStreamInOrder() async {
        let api = FakeAPI()
        let model = SessionViewModel(apkID: "apk-1", api: api)

        await model.start()

        XCTAssertEqual(api.calls, ["runtimeStart", "install:apk-1", "launch:apk-1", "streamStart"])
        XCTAssertEqual(model.state, .live)
        XCTAssertEqual(model.streamStatus?.state, .live)
        XCTAssertNil(model.errorMessage)
    }

    func testStartStopsAtFirstFailure() async {
        let api = FakeAPI()
        api.failAt = "install"
        let model = SessionViewModel(apkID: "apk-2", api: api)

        await model.start()

        XCTAssertEqual(api.calls, ["runtimeStart", "install:apk-2"])
        XCTAssertEqual(model.state, .error)
        XCTAssertNotNil(model.errorMessage)
    }

    func testRefreshStatusUpdatesStreamHealth() async {
        let api = FakeAPI()
        let model = SessionViewModel(apkID: "apk-health", api: api)
        await model.start()
        api.statusState = .error

        await model.refreshStatus()

        XCTAssertEqual(api.calls.last, "streamStatus")
        XCTAssertEqual(model.streamStatus?.state, .error)
        XCTAssertEqual(model.state, .error)
    }

    func testCloseStopsStream() async {
        let api = FakeAPI()
        let model = SessionViewModel(apkID: "apk-3", api: api)
        await model.start()

        await model.close()

        XCTAssertEqual(api.calls.last, "streamStop")
        XCTAssertEqual(model.state, .stopped)
    }
}
