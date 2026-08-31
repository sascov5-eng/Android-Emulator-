import XCTest
@testable import AndroidEmulator

final class InputEncodingTests: XCTestCase {
    func testPointerMessageEncodesNormalizedSchema() throws {
        let data = try InputMessage.pointerDown(x: 0.25, y: 0.75).encodedData()
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(object["type"] as? String, "pointer_down")
        XCTAssertEqual(object["x"] as? Double ?? -1, 0.25, accuracy: 0.0001)
        XCTAssertEqual(object["y"] as? Double ?? -1, 0.75, accuracy: 0.0001)
    }

    func testNavigationMessageEncodesAllowlistedKey() throws {
        let data = try InputMessage.key(.recents).encodedData()
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(object["type"] as? String, "key")
        XCTAssertEqual(object["key"] as? String, "recents")
    }
}
