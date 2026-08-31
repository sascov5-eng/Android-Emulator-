import SwiftUI
import UniformTypeIdentifiers

struct LibraryView: View {
    @AppStorage("backendURL") private var backendURLString = "http://127.0.0.1:8000"
    @StateObject private var viewModel = LibraryViewModel(
        baseURL: URL(string: "http://127.0.0.1:8000")!
    )
    @State private var isImporterPresented = false
    @State private var isSettingsPresented = false

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading && viewModel.items.isEmpty {
                    ProgressView("Loading APKs…")
                } else if let errorMessage = viewModel.errorMessage, viewModel.items.isEmpty {
                    ContentUnavailableView {
                        Label("Connection error", systemImage: "exclamationmark.triangle")
                    } description: {
                        Text(errorMessage)
                    } actions: {
                        Button("Retry") {
                            Task { await viewModel.load() }
                        }
                    }
                } else if viewModel.items.isEmpty {
                    ContentUnavailableView {
                        Label("No APKs yet", systemImage: "shippingbox")
                    } description: {
                        Text("Add an Android APK to upload it to the emulator backend.")
                    } actions: {
                        Button("Add APK") {
                            isImporterPresented = true
                        }
                        .buttonStyle(.borderedProminent)
                    }
                } else {
                    List(viewModel.items) { item in
                        VStack(alignment: .leading, spacing: 5) {
                            Text(item.originalFilename)
                                .font(.headline)
                                .lineLimit(1)

                            HStack(spacing: 10) {
                                Text(ByteCountFormatter.string(fromByteCount: Int64(item.sizeBytes), countStyle: .file))
                                Text(item.createdAt.formatted(date: .abbreviated, time: .shortened))
                            }
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 4)
                    }
                    .refreshable {
                        await viewModel.load()
                    }
                }
            }
            .navigationTitle("Android Emulator")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        isSettingsPresented = true
                    } label: {
                        Label("Settings", systemImage: "gearshape")
                    }
                }

                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        isImporterPresented = true
                    } label: {
                        Label("Add APK", systemImage: "plus")
                    }
                }
            }
        }
        .sheet(isPresented: $isSettingsPresented) {
            NavigationStack {
                SettingsView(backendURLString: $backendURLString)
            }
        }
        .fileImporter(
            isPresented: $isImporterPresented,
            allowedContentTypes: [.data],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case let .success(urls):
                guard let url = urls.first else { return }
                Task { await viewModel.upload(fileURL: url) }
            case let .failure(error):
                print("File importer failed: \(error.localizedDescription)")
            }
        }
        .task {
            applyBackendURL()
            await viewModel.load()
        }
        .onChange(of: backendURLString) { _, _ in
            Task {
                applyBackendURL()
                await viewModel.load()
            }
        }
        .overlay(alignment: .bottom) {
            if let progressText = viewModel.uploadProgressText {
                HStack(spacing: 10) {
                    ProgressView()
                    Text(progressText)
                        .lineLimit(1)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(.regularMaterial, in: Capsule())
                .padding()
            }
        }
    }

    private func applyBackendURL() {
        guard let url = URL(string: backendURLString) else { return }
        viewModel.updateBaseURL(url)
    }
}
