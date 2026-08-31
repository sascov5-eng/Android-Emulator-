import SwiftUI

struct SettingsView: View {
    @Binding var backendURLString: String
    @Environment(\.dismiss) private var dismiss
    @State private var draft: String

    init(backendURLString: Binding<String>) {
        _backendURLString = backendURLString
        _draft = State(initialValue: backendURLString.wrappedValue)
    }

    private var isValidURL: Bool {
        guard let url = URL(string: draft),
              let scheme = url.scheme?.lowercased(),
              ["http", "https"].contains(scheme),
              url.host != nil else {
            return false
        }
        return true
    }

    var body: some View {
        Form {
            Section("Backend") {
                TextField("https://server.example", text: $draft)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()

                if !draft.isEmpty && !isValidURL {
                    Text("Enter a complete http:// or https:// address.")
                        .font(.footnote)
                        .foregroundStyle(.red)
                }
            }

            Section {
                Text("For a real iPhone, this address must point to the backend server reachable from the phone. 127.0.0.1 is only useful for local simulator development.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("Cancel") { dismiss() }
            }
            ToolbarItem(placement: .confirmationAction) {
                Button("Save") {
                    backendURLString = draft.trimmingCharacters(in: .whitespacesAndNewlines)
                    dismiss()
                }
                .disabled(!isValidURL)
            }
        }
    }
}
