import Combine
import Foundation

@MainActor
final class LibraryViewModel: ObservableObject {
    @Published private(set) var items: [APKItem] = []
    @Published private(set) var isLoading = false
    @Published private(set) var uploadProgressText: String?
    @Published private(set) var errorMessage: String?

    private var client: APIClient

    init(baseURL: URL) {
        self.client = APIClient(baseURL: baseURL)
    }

    func updateBaseURL(_ url: URL) {
        client = APIClient(baseURL: url)
    }

    func load() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            items = try await client.listAPKs()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func upload(fileURL: URL) async {
        guard fileURL.pathExtension.lowercased() == "apk" else {
            errorMessage = "Choose a file with the .apk extension."
            return
        }

        let didAccess = fileURL.startAccessingSecurityScopedResource()
        defer {
            if didAccess {
                fileURL.stopAccessingSecurityScopedResource()
            }
        }

        uploadProgressText = "Uploading \(fileURL.lastPathComponent)…"
        errorMessage = nil
        defer { uploadProgressText = nil }

        do {
            let uploaded = try await client.uploadAPK(fileURL: fileURL)
            items.removeAll { $0.id == uploaded.id }
            items.insert(uploaded, at: 0)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
