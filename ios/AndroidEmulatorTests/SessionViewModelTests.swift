import XCTest
@testable import AndroidEmulator

@MainActor
final class SessionViewModelTests: XCTestCase {
    final class FakeAPI: SessionAPI, @unchecked Sendable {
        var calls: [String] = []
        var failAt: String?

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
            return StreamStatus(
                state: .live,
                sessionID: "default",
                whepURL: URL(string: "https://media.example.test/android/session/whep"),
                width: 720,
                height: 1280,
                fps: 30,
                error: nil
            )
        }

        func streamStop() async throws -> StreamStatus {
            calls.append("streamStop")
            return StreamStatus(state: .stopped, sessionID: "default", whepURL: nil, width: 720, height: 1280, fps: 30, error: nil)
        }

        func inputWebSocketURL() -> URL? {
            URL(string: "wss://api.example.test/v1/stream/input")
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

    func testCloseStopsStream() async {
        let api = FakeAPI()
        let model = SessionViewModel(apkID: "apk-3", api: api)
        await model.start()

        await model.close()

        XCTAssertEqual(api.calls.last, "streamStop")
        XCTAssertEqual(model.state, .stopped)
    }
}
