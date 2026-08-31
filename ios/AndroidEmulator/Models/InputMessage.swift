import Foundation

enum NavigationKey: String, Codable, Sendable {
    case back
    case home
    case recents
}

enum InputMessage: Sendable {
    case pointerDown(x: Double, y: Double)
    case pointerMove(x: Double, y: Double)
    case pointerUp(x: Double, y: Double)
    case key(NavigationKey)

    func encodedData() throws -> Data {
        let object: [String: Any]
        switch self {
        case let .pointerDown(x, y):
            object = ["type": "pointer_down", "x": x, "y": y]
        case let .pointerMove(x, y):
            object = ["type": "pointer_move", "x": x, "y": y]
        case let .pointerUp(x, y):
            object = ["type": "pointer_up", "x": x, "y": y]
        case let .key(key):
            object = ["type": "key", "key": key.rawValue]
        }
        return try JSONSerialization.data(withJSONObject: object, options: [])
    }
}
