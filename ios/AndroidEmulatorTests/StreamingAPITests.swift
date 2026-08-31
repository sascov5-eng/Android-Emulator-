import XCTest
@testable import AndroidEmulator

final class StreamingAPITests: XCTestCase {
    func testStreamStatusDecodesBackendJSON() throws {
        let json = """
        {
          "state": "live",
          "session_id": "default",
          "whep_url": "https://media.example.test/android/session/whep",
          "width": 720,
          "height": 1280,
          "fps": 30,
          "error": null
        }
        """.data(using: .utf8)!

        let status = try JSONDecoder.androidEmulatorDecoder.decode(StreamStatus.self, from: json)

        XCTAssertEqual(status.state, .live)
        XCTAssertEqual(status.sessionID, "default")
        XCTAssertEqual(status.whepURL, URL(string: "https://media.example.test/android/session/whep"))
        XCTAssertEqual(status.width, 720)
        XCTAssertEqual(status.height, 1280)
        XCTAssertEqual(status.fps, 30)
    }

    func testInputWebSocketURLUsesSecureSchemeForHTTPS() {
        let client = APIClient(baseURL: URL(string: "https://api.example.test")!)
        XCTAssertEqual(client.inputWebSocketURL(), URL(string: "wss://api.example.test/v1/stream/input"))
    }

    func testInputWebSocketURLUsesWSForHTTP() {
        let client = APIClient(baseURL: URL(string: "http://127.0.0.1:8000")!)
        XCTAssertEqual(client.inputWebSocketURL(), URL(string: "ws://127.0.0.1:8000/v1/stream/input"))
    }
}
