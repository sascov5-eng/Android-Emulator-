import SwiftUI

@MainActor
struct SessionView: View {
    let apk: APKItem

    @Environment(\.dismiss) private var dismiss
    @StateObject private var viewModel: SessionViewModel
    private let apiClient: APIClient

    @State private var inputSocket: InputSocket?
    @State private var pointerActive = false
    @State private var lastPointerPoint: CGPoint?
    @State private var controlsVisible = true

    init(apk: APKItem, baseURL: URL) {
        self.apk = apk
        let client = APIClient(baseURL: baseURL)
        self.apiClient = client
        _viewModel = StateObject(wrappedValue: SessionViewModel(apkID: apk.id, api: client))
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            GeometryReader { geometry in
                ZStack {
                    if let status = viewModel.streamStatus,
                       status.state == .live,
                       let whepURL = status.whepURL {
                        WHEPWebView(whepURL: whepURL)
                            .ignoresSafeArea()

                        gestureSurface(containerSize: geometry.size, status: status)
                    } else {
                        Color.black
                    }

                    statusOverlay
                }
            }

            if controlsVisible {
                sessionChrome
            }
        }
        .statusBarHidden(!controlsVisible)
        .task {
            await beginSessionIfNeeded()
            await monitorStreamHealth()
        }
        .onDisappear {
            inputSocket?.close()
            inputSocket = nil
            Task { await viewModel.close() }
        }
    }

    private var statusOverlay: some View {
        Group {
            switch viewModel.state {
            case .idle, .starting:
                VStack(spacing: 12) {
                    ProgressView()
                        .tint(.white)
                    Text("Starting Android…")
                        .foregroundStyle(.white)
                }
                .padding(20)
                .background(.black.opacity(0.65), in: RoundedRectangle(cornerRadius: 16))

            case .error:
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.title)
                    Text(viewModel.errorMessage ?? "Android session failed")
                        .multilineTextAlignment(.center)
                    Button("Retry") {
                        Task { await restartSession() }
                    }
                    .buttonStyle(.borderedProminent)
                }
                .foregroundStyle(.white)
                .padding(20)
                .background(.black.opacity(0.75), in: RoundedRectangle(cornerRadius: 16))
                .padding()

            case .live, .stopped:
                EmptyView()
            }
        }
    }

    private var sessionChrome: some View {
        VStack {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(apk.originalFilename)
                        .font(.headline)
                        .lineLimit(1)
                    Text(viewModel.state == .live ? "Android Live" : "Android Session")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                Button {
                    controlsVisible = false
                } label: {
                    Image(systemName: "arrow.up.left.and.arrow.down.right")
                }
                .buttonStyle(.bordered)

                Button {
                    Task {
                        inputSocket?.close()
                        inputSocket = nil
                        await viewModel.close()
                        dismiss()
                    }
                } label: {
                    Image(systemName: "xmark")
                }
                .buttonStyle(.bordered)
            }
            .padding(12)
            .background(.regularMaterial)

            Spacer()

            HStack(spacing: 42) {
                navigationButton(.back, systemName: "chevron.left")
                navigationButton(.home, systemName: "circle")
                navigationButton(.recents, systemName: "square.on.square")
            }
            .font(.title3)
            .padding(.horizontal, 28)
            .padding(.vertical, 12)
            .background(.regularMaterial, in: Capsule())
            .padding(.bottom, 12)
        }
    }

    @ViewBuilder
    private func gestureSurface(containerSize: CGSize, status: StreamStatus) -> some View {
        Color.clear
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0, coordinateSpace: .local)
                    .onChanged { value in
                        guard let point = VideoGeometry.normalizedPoint(
                            touch: value.location,
                            container: containerSize,
                            video: CGSize(width: status.width, height: status.height)
                        ) else {
                            return
                        }

                        let x = Double(point.x)
                        let y = Double(point.y)
                        if pointerActive {
                            send(.pointerMove(x: x, y: y))
                        } else {
                            pointerActive = true
                            send(.pointerDown(x: x, y: y))
                        }
                        lastPointerPoint = point
                    }
                    .onEnded { value in
                        guard pointerActive else { return }
                        let resolved = VideoGeometry.normalizedPoint(
                            touch: value.location,
                            container: containerSize,
                            video: CGSize(width: status.width, height: status.height)
                        ) ?? lastPointerPoint

                        if let point = resolved {
                            send(.pointerUp(x: Double(point.x), y: Double(point.y)))
                        }
                        pointerActive = false
                        lastPointerPoint = nil
                    }
            )
            .onTapGesture(count: 2) {
                controlsVisible.toggle()
            }
    }

    private func navigationButton(_ key: NavigationKey, systemName: String) -> some View {
        Button {
            send(.key(key))
        } label: {
            Image(systemName: systemName)
                .frame(width: 38, height: 38)
        }
        .buttonStyle(.plain)
        .disabled(viewModel.state != .live)
    }

    private func beginSessionIfNeeded() async {
        guard viewModel.state == .idle || viewModel.state == .stopped else { return }
        await viewModel.start()
        if viewModel.state == .live {
            connectInputIfNeeded()
        }
    }

    private func restartSession() async {
        inputSocket?.close()
        inputSocket = nil
        await viewModel.start()
        if viewModel.state == .live {
            connectInputIfNeeded()
        }
    }

    private func monitorStreamHealth() async {
        while !Task.isCancelled {
            try? await Task.sleep(for: .seconds(5))
            guard !Task.isCancelled else { return }
            if viewModel.state == .live || viewModel.state == .error {
                await viewModel.refreshStatus()
                if viewModel.state == .live {
                    connectInputIfNeeded()
                }
            }
        }
    }

    private func connectInputIfNeeded() {
        guard inputSocket == nil, let url = apiClient.inputWebSocketURL() else { return }
        let socket = InputSocket(url: url)
        inputSocket = socket
        socket.connect()
    }

    private func send(_ message: InputMessage) {
        guard viewModel.state == .live else { return }
        inputSocket?.send(message)
    }
}
