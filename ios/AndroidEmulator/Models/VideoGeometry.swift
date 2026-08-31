import CoreGraphics

enum VideoGeometry {
    static func normalizedPoint(
        touch: CGPoint,
        container: CGSize,
        video: CGSize
    ) -> CGPoint? {
        guard container.width > 0,
              container.height > 0,
              video.width > 0,
              video.height > 0 else {
            return nil
        }

        let scale = min(container.width / video.width, container.height / video.height)
        let fitted = CGSize(width: video.width * scale, height: video.height * scale)
        let origin = CGPoint(
            x: (container.width - fitted.width) / 2,
            y: (container.height - fitted.height) / 2
        )

        guard touch.x >= origin.x,
              touch.y >= origin.y,
              touch.x <= origin.x + fitted.width,
              touch.y <= origin.y + fitted.height else {
            return nil
        }

        return CGPoint(
            x: (touch.x - origin.x) / fitted.width,
            y: (touch.y - origin.y) / fitted.height
        )
    }
}
