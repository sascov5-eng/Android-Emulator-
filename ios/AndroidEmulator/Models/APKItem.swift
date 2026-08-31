import Foundation

struct APKItem: Codable, Identifiable, Equatable, Sendable {
    let id: String
    let originalFilename: String
    let sha256: String
    let sizeBytes: Int
    let createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case originalFilename = "original_filename"
        case sha256
        case sizeBytes = "size_bytes"
        case createdAt = "created_at"
    }
}

extension JSONDecoder {
    static var androidEmulatorDecoder: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let value = try container.decode(String.self)

            let fractional = ISO8601DateFormatter()
            fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = fractional.date(from: value) {
                return date
            }

            let standard = ISO8601DateFormatter()
            standard.formatOptions = [.withInternetDateTime]
            if let date = standard.date(from: value) {
                return date
            }

            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Invalid ISO-8601 date: \(value)"
            )
        }
        return decoder
    }
}
