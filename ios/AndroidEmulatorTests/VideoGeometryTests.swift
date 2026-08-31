import CoreGraphics
import XCTest
@testable import AndroidEmulator

final class VideoGeometryTests: XCTestCase {
    func testPortraitAspectFitMapsCenterAndRejectsLetterbox() {
        let container = CGSize(width: 390, height: 844)
        let video = CGSize(width: 720, height: 1280)

        let center = VideoGeometry.normalizedPoint(
            touch: CGPoint(x: 195, y: 422),
            container: container,
            video: video
        )
        XCTAssertEqual(center?.x ?? -1, 0.5, accuracy: 0.001)
        XCTAssertEqual(center?.y ?? -1, 0.5, accuracy: 0.001)

        XCTAssertNil(VideoGeometry.normalizedPoint(
            touch: CGPoint(x: 195, y: 10),
            container: container,
            video: video
        ))
    }

    func testLandscapeAspectFitMapsCenterAndRejectsPillarbox() {
        let container = CGSize(width: 844, height: 390)
        let video = CGSize(width: 1280, height: 720)

        let center = VideoGeometry.normalizedPoint(
            touch: CGPoint(x: 422, y: 195),
            container: container,
            video: video
        )
        XCTAssertEqual(center?.x ?? -1, 0.5, accuracy: 0.001)
        XCTAssertEqual(center?.y ?? -1, 0.5, accuracy: 0.001)

        XCTAssertNil(VideoGeometry.normalizedPoint(
            touch: CGPoint(x: 10, y: 195),
            container: container,
            video: video
        ))
    }
}
