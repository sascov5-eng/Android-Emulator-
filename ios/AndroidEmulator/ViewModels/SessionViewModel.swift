import Foundation

@MainActor
final class SessionViewModel: ObservableObject {
    enum State: Equatable {
        case idle
        case starting
        case live
        case error
        case stopped
    }

    let apkID: String
    let api: any SessionAPI

    @Published private(set) var state: State = .idle
    @Published private(set) var streamStatus: StreamStatus?
    @Published private(set) var errorMessage: String?

    init(apkID: String, api: any SessionAPI) {
        self.apkID = apkID
        self.api = api
    }

    func start() async {
        state = .starting
        streamStatus = nil
        errorMessage = nil

        do {
            _ = try await api.runtimeStart()
            _ = try await api.install(apkID: apkID)
            _ = try await api.launch(apkID: apkID)
            let status = try await api.streamStart()
            streamStatus = status
            guard status.state == .live else {
                throw SessionViewModelError.streamNotLive
            }
            state = .live
        } catch {
            state = .error
            errorMessage = Self.publicMessage(for: error)
        }
    }

    func refreshStatus() async {
        guard state == .live || state == .error else { return }
        do {
            let status = try await api.streamStatus()
            streamStatus = status
            switch status.state {
            case .live:
                state = .live
                errorMessage = nil
            case .error:
                state = .error
                errorMessage = status.error ?? "Android stream is unavailable."
            case .starting:
                state = .starting
            case .stopped:
                state = .stopped
            }
        } catch {
            state = .error
            errorMessage = Self.publicMessage(for: error)
        }
    }

    func close() async {
        do {
            streamStatus = try await api.streamStop()
        } catch {
            errorMessage = Self.publicMessage(for: error)
        }
        state = .stopped
    }

    private static func publicMessage(for error: Error) -> String {
        (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
    }
}

private enum SessionViewModelError: LocalizedError {
    case streamNotLive

    var errorDescription: String? {
        "Android stream did not become live."
    }
}
