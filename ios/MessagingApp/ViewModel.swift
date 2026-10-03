import Foundation
import Combine
import MessagingCore

@MainActor
final class ViewModel: ObservableObject {
    @Published var username: String?
    @Published var messages: [MessageSnapshot] = []
    @Published var pendingCount: Int = 0
    @Published var syncState: String = "idle"
    @Published var serverEpoch: String?
    @Published var error: String?

    private let client: MessagingClient
    private var syncTask: Task<Void, Never>?

    init(client: MessagingClient) {
        self.client = client
        Task { await self.start() }
    }

    private func start() async {
        try? await client.load()
        await refresh()
        startSyncLoop()
    }

    func identify(name: String) {
        Task {
            do {
                _ = try await client.identify(name: name)
                await refresh()
            } catch {
                self.error = error.localizedDescription
            }
        }
    }

    func send(recipient: String, text: String) {
        Task {
            do {
                _ = try await client.enqueue(recipient: recipient, text: text)
                await refresh()
            } catch {
                self.error = error.localizedDescription
            }
        }
    }

    func syncOnce() {
        Task {
            _ = try? await client.syncOnce()
            await refresh()
        }
    }

    func clearError() { error = nil }

    private func startSyncLoop() {
        syncTask?.cancel()
        syncTask = Task {
            while !Task.isCancelled {
                _ = try? await client.syncOnce()
                await refresh()
                try? await Task.sleep(nanoseconds: 3_000_000_000)
            }
        }
    }

    private func refresh() async {
        let snap = try? await client.snapshot(peer: nil)
        guard let snap else { return }
        username = snap.username
        messages = snap.messages
        pendingCount = snap.pendingCount
        syncState = snap.syncState
        serverEpoch = snap.serverEpoch
    }
}
