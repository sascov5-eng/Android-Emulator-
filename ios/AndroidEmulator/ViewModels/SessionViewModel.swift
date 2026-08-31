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
            errorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    func close() async {
        do {
            streamStatus = try await api.streamStop()
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
        state = .stopped
    }
}

private enum SessionViewModelError: LocalizedError {
    case streamNotLive

    var errorDescription: String? {
        "Android stream did not become live."
    }
}
