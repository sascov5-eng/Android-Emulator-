import Foundation

enum RuntimeState: String, Codable, Sendable {
    case stopped
    case starting
    case ready
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

enum StreamState: String, Codable, Sendable {
    case stopped
    case starting
    case live
    case error
}

struct StreamStatus: Codable, Equatable, Sendable {
    let state: StreamState
    let sessionID: String
    let whepURL: URL?
    let width: Int
    let height: Int
    let fps: Int
    let error: String?

    enum CodingKeys: String, CodingKey {
        case state
        case sessionID = "session_id"
        case whepURL = "whep_url"
        case width
        case height
        case fps
        case error
    }

    var viewerURL: URL? {
        guard let whepURL else { return nil }
        return whepURL.deletingLastPathComponent()
    }
}

enum SessionState: Equatable, Sendable {
    case idle
    case starting
    case live
    case stopping
    case stopped
    case error
}

protocol SessionAPI: Sendable {
    func runtimeStart() async throws -> RuntimeStatus
    func install(apkID: String) async throws -> AndroidApp
    func launch(apkID: String) async throws -> AndroidApp
    func streamStart() async throws -> StreamStatus
    func streamStop() async throws -> StreamStatus
    func inputWebSocketURL() -> URL?
}
