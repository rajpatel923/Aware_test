import Foundation

/// The main client facade.  All state mutation is serialised by the actor.
public actor MessagingClient {
    private let store: any ChatStore
    private let transport: any MessagingTransport
    private let pageSize: Int

    private var syncState: SyncStateRecord = SyncStateRecord()
    private var username: String?
    private var offline: Bool = false
    private var faultDropNext: String? = nil

    public init(store: any ChatStore, transport: any MessagingTransport, pageSize: Int = 100) {
        self.store = store
        self.transport = transport
        self.pageSize = pageSize
    }

    /// Reload persisted state — call once after construction.
    public func load() async throws {
        username = try await store.loadIdentity()
        syncState = try await store.loadSyncState()
    }

    // MARK: - Commands

    public func identify(name: String) async throws -> String {
        let u = try Username(name)
        try await store.saveIdentity(u.value)
        username = u.value
        return u.value
    }

    public func enqueue(recipient: String, text: String) async throws -> String {
        let r = try Username(recipient)
        guard !text.isEmpty, text.utf8.count <= 4096 else {
            throw MessagingError.invalidRequest("Text must be 1–4096 UTF-8 bytes")
        }
        guard let sender = username else {
            throw MessagingError.invalidRequest("Not identified")
        }
        let mid = UUID().uuidString.lowercased()
        try await store.enqueue(id: mid, sender: sender, recipient: r.value, text: text)
        return mid
    }

    public func setOffline(_ enabled: Bool) async {
        offline = enabled
    }

    public func fault(drop: String) async {
        faultDropNext = drop
    }

    public func syncOnce() async throws -> (outcome: String, accepted: Int, received: Int, pending: Int) {
        if offline {
            let pending = (try? await store.pendingMessages())?.count ?? 0
            return ("paused", 0, 0, pending)
        }

        // §10.2: adopt epoch from meta if we don't have one
        if syncState.epoch == nil {
            do {
                let meta = try await transport.fetchMeta()
                syncState.epoch = meta.serverEpoch
                try await store.updateEpoch(active: meta.serverEpoch, pending: nil)
            } catch {
                let pending = (try? await store.pendingMessages())?.count ?? 0
                return ("backoff", 0, 0, pending)
            }
        }

        let epoch = syncState.epoch!
        var accepted = 0
        var received = 0

        // §11.2: inbox first, then outbox
        // Fetch inbox
        if let uname = username {
            var fetchMore = true
            while fetchMore {
                let resp: InboxResponse
                do {
                    resp = try await transport.fetchInbox(
                        username: uname, after: syncState.cursor,
                        limit: pageSize, epoch: epoch
                    )
                } catch MessagingError.epochChanged(let newEpoch) {
                    syncState.pendingEpoch = newEpoch
                    try await store.updateEpoch(active: syncState.epoch, pending: newEpoch)
                    let pending = (try? await store.pendingMessages())?.count ?? 0
                    return ("server_reset", accepted, received, pending)
                } catch {
                    let pending = (try? await store.pendingMessages())?.count ?? 0
                    return ("backoff", accepted, received, pending)
                }

                // Fault injection after receiving response
                if faultDropNext == "inbox" {
                    faultDropNext = nil
                    let pending = (try? await store.pendingMessages())?.count ?? 0
                    return ("backoff", accepted, received, pending)
                }

                // §7.2: validate page
                guard !(resp.messages.isEmpty && resp.hasMore) else {
                    throw MessagingError.protocolError("Empty page claims has_more")
                }
                if let last = resp.messages.last {
                    guard resp.nextCursor == last.sequence else {
                        throw MessagingError.protocolError("next_cursor mismatch")
                    }
                    var prevSeq = syncState.cursor
                    for msg in resp.messages {
                        guard msg.sequence > prevSeq else {
                            throw MessagingError.protocolError("Sequences not strictly increasing")
                        }
                        prevSeq = msg.sequence
                    }
                }

                if !resp.messages.isEmpty {
                    let beforeCount = (try? await store.snapshot(peer: nil))?.messages.filter { $0.status == "accepted" }.count ?? 0
                    try await store.commitPage(messages: resp.messages, cursor: resp.nextCursor)
                    let afterCount = (try? await store.snapshot(peer: nil))?.messages.filter { $0.status == "accepted" }.count ?? 0
                    received += max(0, afterCount - beforeCount)
                    syncState.cursor = resp.nextCursor
                }

                fetchMore = resp.hasMore
            }
        }

        // Submit outbox entries (up to 10 per §11.2)
        let pending = try await store.pendingMessages()
        let batch = Array(pending.prefix(10))
        for msg in batch {
            let req = SubmitRequest(
                clientMessageID: msg.id,
                sender: msg.sender,
                recipient: msg.recipient,
                text: msg.text,
                expectedEpoch: epoch
            )
            do {
                let resp = try await transport.submit(req)

                // Fault injection after receiving response
                if faultDropNext == "submit" {
                    faultDropNext = nil
                    let pendingCount = (try? await store.pendingMessages())?.count ?? 0
                    return ("backoff", accepted, received, pendingCount)
                }

                try await store.acknowledgeMessage(
                    id: msg.id,
                    sequence: resp.sequence,
                    acceptedAt: resp.acceptedAt
                )
                accepted += 1
            } catch MessagingError.epochChanged(let newEpoch) {
                syncState.pendingEpoch = newEpoch
                try await store.updateEpoch(active: syncState.epoch, pending: newEpoch)
                let pendingCount = (try? await store.pendingMessages())?.count ?? 0
                return ("server_reset", accepted, received, pendingCount)
            } catch MessagingError.conflict(let code) {
                try await store.failMessage(id: msg.id, code: code)
                continue
            } catch {
                let pendingCount = (try? await store.pendingMessages())?.count ?? 0
                return ("backoff", accepted, received, pendingCount)
            }
        }

        let pendingCount = (try? await store.pendingMessages())?.count ?? 0
        return ("ok", accepted, received, pendingCount)
    }

    public func snapshot(peer: String?) async throws -> ChatSnapshot {
        var result = try await store.snapshot(peer: peer)
        // inject live offline state
        return ChatSnapshot(
            username: result.username,
            serverEpoch: result.serverEpoch,
            cursor: result.cursor,
            syncState: offline ? "offline" : "online",
            pendingCount: result.pendingCount,
            messages: result.messages
        )
    }

    public func resetSession() async throws -> (epoch: String, cursor: Int) {
        let newEpoch: String
        if let pending = syncState.pendingEpoch {
            newEpoch = pending
        } else {
            let meta = try await transport.fetchMeta()
            newEpoch = meta.serverEpoch
        }
        syncState = SyncStateRecord(epoch: newEpoch, pendingEpoch: nil, cursor: 0)
        try await store.resetSession(epoch: newEpoch)
        return (newEpoch, 0)
    }
}
