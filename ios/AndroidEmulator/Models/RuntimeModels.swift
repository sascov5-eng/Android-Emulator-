import Foundation

enum RuntimeState: String, Codable, Equatable, Sendable {
    case stopped
    case starting
    case ready
    case stopping
    case error
}

struct RuntimeStatus: Codable, Equatable, Sendable {
    let state: RuntimeState
    let adbTarget: String?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case state
        case adbTarget = "adb_target"
        case error
    }
}

struct AndroidApp: Codable, Equatable, Sendable {
    let packageName: String
    let activityName: String?
    let label: String?

    enum CodingKeys: String, CodingKey {
        case packageName = "package_name"
        case activityName = "activity_name"
        case label
    }
}
