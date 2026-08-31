import CoreGraphics

enum VideoGeometry {
    static func contentRect(container: CGSize, video: CGSize) -> CGRect? {
        guard container.width > 0, container.height > 0, video.width > 0, video.height > 0 else {
            return nil
        }

        let scale = min(container.width / video.width, container.height / video.height)
        let fitted = CGSize(width: video.width * scale, height: video.height * scale)
        return CGRect(
            x: (container.width - fitted.width) / 2,
            y: (container.height - fitted.height) / 2,
            width: fitted.width,
            height: fitted.height
        )
    }

    static func normalizedPoint(touch: CGPoint, container: CGSize, video: CGSize) -> CGPoint? {
        guard let rect = contentRect(container: container, video: video), rect.contains(touch) else {
            return nil
        }
        return CGPoint(
            x: min(1, max(0, (touch.x - rect.minX) / rect.width)),
            y: min(1, max(0, (touch.y - rect.minY) / rect.height))
        )
    }
}
