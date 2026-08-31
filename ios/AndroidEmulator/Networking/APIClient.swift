import Foundation

private struct APIErrorPayload: Decodable {
    let code: String?
    let message: String?
}

enum APIClientError: LocalizedError {
    case invalidResponse
    case invalidWebSocketURL
    case server(code: String?, message: String, statusCode: Int)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "The backend returned an invalid response."
        case .invalidWebSocketURL:
            return "The backend WebSocket URL is invalid."
        case let .server(code, message, statusCode):
            if let code, !code.isEmpty {
                return "\(message) (\(code), HTTP \(statusCode))"
            }
            return "\(message) (HTTP \(statusCode))"
        }
    }
}

protocol SessionAPI: Sendable {
    func runtimeStart() async throws -> RuntimeStatus
    func install(apkID: String) async throws -> AndroidApp
    func launch(apkID: String) async throws -> AndroidApp
    func streamStart() async throws -> StreamStatus
    func streamStop() async throws -> StreamStatus
    func inputWebSocketURL() -> URL?
}

final class APIClient: @unchecked Sendable, SessionAPI {
    let baseURL: URL
    private let session: URLSession

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func endpoint(_ path: String) -> URL {
        guard let url = URL(string: path, relativeTo: baseURL)?.absoluteURL else {
            preconditionFailure("Invalid API endpoint path: \(path)")
        }
        return url
    }

    func listAPKs() async throws -> [APKItem] {
        try await request([APKItem].self, method: "GET", url: endpoint("/v1/apks"))
    }

    func uploadAPK(fileURL: URL) async throws -> APKItem {
        let fileData = try Data(contentsOf: fileURL)
        let boundary = "Boundary-\(UUID().uuidString)"
        let filename = fileURL.lastPathComponent.replacingOccurrences(of: "\"", with: "")

        var body = Data()
        body.appendUTF8("--\(boundary)\r\n")
        body.appendUTF8("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n")
        body.appendUTF8("Content-Type: application/vnd.android.package-archive\r\n\r\n")
        body.append(fileData)
        body.appendUTF8("\r\n--\(boundary)--\r\n")

        var request = URLRequest(url: endpoint("/v1/apks"))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let (data, response) = try await session.upload(for: request, from: body)
        return try decode(APKItem.self, data: data, response: response)
    }

    func runtimeStart() async throws -> RuntimeStatus {
        try await request(RuntimeStatus.self, method: "POST", url: endpoint("/v1/runtime/start"))
    }

    func install(apkID: String) async throws -> AndroidApp {
        let url = endpoint("/v1/runtime/install").appendingPathComponent(apkID)
        return try await request(AndroidApp.self, method: "POST", url: url)
    }

    func launch(apkID: String) async throws -> AndroidApp {
        let url = endpoint("/v1/runtime/launch").appendingPathComponent(apkID)
        return try await request(AndroidApp.self, method: "POST", url: url)
    }

    func streamStart() async throws -> StreamStatus {
        try await request(StreamStatus.self, method: "POST", url: endpoint("/v1/stream/start"))
    }

    func streamStatus() async throws -> StreamStatus {
        try await request(StreamStatus.self, method: "GET", url: endpoint("/v1/stream/status"))
    }

    func streamStop() async throws -> StreamStatus {
        try await request(StreamStatus.self, method: "POST", url: endpoint("/v1/stream/stop"))
    }

    func inputWebSocketURL() -> URL? {
        guard var components = URLComponents(url: endpoint("/v1/stream/input"), resolvingAgainstBaseURL: false) else {
            return nil
        }
        switch components.scheme?.lowercased() {
        case "https":
            components.scheme = "wss"
        case "http":
            components.scheme = "ws"
        case "wss", "ws":
            break
        default:
            return nil
        }
        return components.url
    }

    private func request<T: Decodable>(_ type: T.Type, method: String, url: URL) async throws -> T {
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await session.data(for: request)
        return try decode(type, data: data, response: response)
    }

    private func decode<T: Decodable>(_ type: T.Type, data: Data, response: URLResponse) throws -> T {
        guard let http = response as? HTTPURLResponse else {
            throw APIClientError.invalidResponse
        }

        guard (200..<300).contains(http.statusCode) else {
            let payload = try? JSONDecoder().decode(APIErrorPayload.self, from: data)
            throw APIClientError.server(
                code: payload?.code,
                message: payload?.message ?? "Backend request failed",
                statusCode: http.statusCode
            )
        }

        return try JSONDecoder.androidEmulatorDecoder.decode(type, from: data)
    }
}

private extension Data {
    mutating func appendUTF8(_ string: String) {
        append(Data(string.utf8))
    }
}
