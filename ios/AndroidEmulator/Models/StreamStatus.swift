import Foundation

enum StreamState: String, Codable, Equatable, Sendable {
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
}
