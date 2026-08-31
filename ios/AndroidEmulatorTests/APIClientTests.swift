import XCTest
@testable import AndroidEmulator

final class APIClientTests: XCTestCase {
    func testAPKItemDecodesBackendJSON() throws {
        let json = """
        {
          "id": "apk-1",
          "original_filename": "demo.apk",
          "sha256": "abc123",
          "size_bytes": 42,
          "created_at": "2026-08-31T18:00:00Z"
        }
        """.data(using: .utf8)!

        let item = try JSONDecoder.androidEmulatorDecoder.decode(APKItem.self, from: json)

        XCTAssertEqual(item.id, "apk-1")
        XCTAssertEqual(item.originalFilename, "demo.apk")
        XCTAssertEqual(item.sizeBytes, 42)
    }

    func testEndpointResolvesAgainstBaseURL() {
        let client = APIClient(baseURL: URL(string: "https://example.test")!)

        XCTAssertEqual(
            client.endpoint("/v1/apks"),
            URL(string: "https://example.test/v1/apks")!
        )
    }
}
