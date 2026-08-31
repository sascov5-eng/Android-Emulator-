import XCTest
@testable import AndroidEmulator

final class StreamSessionTests: XCTestCase {
    func testStreamSessionDecodesBackendPayload() throws {
        let json = """
        {
          "state": "live",
          "viewer_url": "https://example.test:8889/session/",
          "whep_url": "https://example.test:8889/session/whep",
          "input_ws_path": "/v1/stream/input",
          "width": 1080,
          "height": 1920,
          "fps": 30
        }
        """.data(using: .utf8)!

        let session = try JSONDecoder.androidEmulatorDecoder.decode(StreamSession.self, from: json)

        XCTAssertEqual(session.state, .live)
        XCTAssertEqual(session.viewerURL.absoluteString, "https://example.test:8889/session/")
        XCTAssertEqual(session.whepURL.absoluteString, "https://example.test:8889/session/whep")
        XCTAssertEqual(session.inputWebSocketPath, "/v1/stream/input")
        XCTAssertEqual(session.width, 1080)
        XCTAssertEqual(session.height, 1920)
        XCTAssertEqual(session.fps, 30)
    }

    func testInputWebSocketURLUsesBackendSchemeAndHost() throws {
        let session = StreamSession(
            state: .live,
            viewerURL: URL(string: "https://stream.example.test/session/")!,
            whepURL: URL(string: "https://stream.example.test/session/whep")!,
            inputWebSocketPath: "/v1/stream/input",
            width: 1080,
            height: 1920,
            fps: 30,
            error: nil
        )

        let url = try session.inputWebSocketURL(baseURL: URL(string: "https://api.example.test:8000")!)
        XCTAssertEqual(url.absoluteString, "wss://api.example.test:8000/v1/stream/input")
    }

    func testInputWebSocketURLUsesWSForHTTPBackend() throws {
        let session = StreamSession(
            state: .live,
            viewerURL: URL(string: "http://10.0.0.4:8889/session/")!,
            whepURL: URL(string: "http://10.0.0.4:8889/session/whep")!,
            inputWebSocketPath: "/v1/stream/input",
            width: 720,
            height: 1280,
            fps: 30,
            error: nil
        )

        let url = try session.inputWebSocketURL(baseURL: URL(string: "http://10.0.0.4:8000")!)
        XCTAssertEqual(url.absoluteString, "ws://10.0.0.4:8000/v1/stream/input")
    }
}
