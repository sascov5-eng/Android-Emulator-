import Foundation

enum NavigationKey: String, Sendable {
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
        return try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
    }
}

@MainActor
final class InputSocket: ObservableObject {
    enum State: Equatable {
        case disconnected
        case connecting
        case connected
        case failed
    }

    @Published private(set) var state: State = .disconnected

    private let url: URL
    private let session: URLSession
    private var task: URLSessionWebSocketTask?
    private var reconnectTask: Task<Void, Never>?
    private var reconnectAttempt = 0
    private let maxReconnectAttempts = 4
    private var intentionallyClosed = false

    init(url: URL, session: URLSession = .shared) {
        self.url = url
        self.session = session
    }

    func connect() {
        guard task == nil else { return }
        intentionallyClosed = false
        state = .connecting
        let socket = session.webSocketTask(with: url)
        task = socket
        socket.resume()
        state = .connected
        reconnectAttempt = 0
        listen()
    }

    func send(_ message: InputMessage) {
        guard let task else {
            scheduleReconnect()
            return
        }
        do {
            let data = try message.encodedData()
            guard let string = String(data: data, encoding: .utf8) else { return }
            task.send(.string(string)) { [weak self] error in
                guard error != nil else { return }
                Task { @MainActor in
                    self?.handleDisconnect()
                }
            }
        } catch {
            state = .failed
        }
    }

    func close() {
        intentionallyClosed = true
        reconnectTask?.cancel()
        reconnectTask = nil
        task?.cancel(with: .normalClosure, reason: nil)
        task = nil
        state = .disconnected
    }

    private func listen() {
        task?.receive { [weak self] result in
            Task { @MainActor in
                guard let self else { return }
                switch result {
                case .success:
                    self.listen()
                case .failure:
                    self.handleDisconnect()
                }
            }
        }
    }

    private func handleDisconnect() {
        task = nil
        if intentionallyClosed {
            state = .disconnected
            return
        }
        state = .disconnected
        scheduleReconnect()
    }

    private func scheduleReconnect() {
        guard !intentionallyClosed, reconnectAttempt < maxReconnectAttempts, reconnectTask == nil else {
            if reconnectAttempt >= maxReconnectAttempts {
                state = .failed
            }
            return
        }

        reconnectAttempt += 1
        let delay = min(pow(2.0, Double(reconnectAttempt - 1)), 8.0)
        reconnectTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(delay))
            guard !Task.isCancelled else { return }
            await MainActor.run {
                guard let self else { return }
                self.reconnectTask = nil
                self.connect()
            }
        }
    }
}
