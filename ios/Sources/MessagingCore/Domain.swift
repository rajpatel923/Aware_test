import Foundation

// MARK: - Value types

public struct Username: Hashable, Sendable, CustomStringConvertible {
    public let value: String

    public init(_ raw: String) throws {
        // §2.1: trim ASCII space/tab/CR/LF
        var s = raw
        while let c = s.first, c == " " || c == "\t" || c == "\r" || c == "\n" { s.removeFirst() }
        while let c = s.last,  c == " " || c == "\t" || c == "\r" || c == "\n" { s.removeLast() }
        // §2.1: ASCII-only lowercase — never locale-aware
        var scv = String.UnicodeScalarView()
        for sc in s.unicodeScalars {
            scv.append((sc.value >= 65 && sc.value <= 90) ? Unicode.Scalar(sc.value + 32)! : sc)
        }
        let lower = String(scv)
        // §2.2: 1–32 chars of [a-z0-9_]
        guard !lower.isEmpty, lower.count <= 32,
              lower.unicodeScalars.allSatisfy({ sc in
                  let v = sc.value
                  return (v >= 97 && v <= 122) || (v >= 48 && v <= 57) || v == 95
              })
        else { throw MessagingError.invalidRequest("Invalid username: \(raw)") }
        value = lower
    }

    public var description: String { value }
}

public struct PendingMessage: Sendable {
    public let id: String
    public let sender: String
    public let recipient: String
    public let text: String
    public init(id: String, sender: String, recipient: String, text: String) {
        self.id = id; self.sender = sender; self.recipient = recipient; self.text = text
    }
}

public struct IncomingMessage: Sendable {
    public let clientMessageID: String
    public let sender: String
    public let recipient: String
    public let text: String
    public let sequence: Int
    public init(clientMessageID: String, sender: String, recipient: String, text: String, sequence: Int) {
        self.clientMessageID = clientMessageID; self.sender = sender
        self.recipient = recipient; self.text = text; self.sequence = sequence
    }
}

public struct SyncStateRecord: Sendable {
    public var epoch: String?
    public var pendingEpoch: String?
    public var cursor: Int

    public init(epoch: String? = nil, pendingEpoch: String? = nil, cursor: Int = 0) {
        self.epoch = epoch; self.pendingEpoch = pendingEpoch; self.cursor = cursor
    }
}

public struct MessageSnapshot: Sendable {
    public let clientMessageID: String
    public let sender: String
    public let recipient: String
    public let text: String
    public let status: String
    public let sequence: Int?
    public let errorCode: String?
    public init(clientMessageID: String, sender: String, recipient: String, text: String,
                status: String, sequence: Int?, errorCode: String?) {
        self.clientMessageID = clientMessageID; self.sender = sender; self.recipient = recipient
        self.text = text; self.status = status; self.sequence = sequence; self.errorCode = errorCode
    }
}

public struct ChatSnapshot: Sendable {
    public let username: String?
    public let serverEpoch: String?
    public let cursor: Int
    public let syncState: String
    public let pendingCount: Int
    public let messages: [MessageSnapshot]
    public init(username: String?, serverEpoch: String?, cursor: Int,
                syncState: String, pendingCount: Int, messages: [MessageSnapshot]) {
        self.username = username; self.serverEpoch = serverEpoch; self.cursor = cursor
        self.syncState = syncState; self.pendingCount = pendingCount; self.messages = messages
    }
}

// MARK: - Transport I/O types

public struct MetaResponse: Sendable {
    public let serverEpoch: String
    public init(serverEpoch: String) { self.serverEpoch = serverEpoch }
}

public struct SubmitRequest: Sendable {
    public let clientMessageID: String
    public let sender: String
    public let recipient: String
    public let text: String
    public let expectedEpoch: String
    public init(clientMessageID: String, sender: String, recipient: String,
                text: String, expectedEpoch: String) {
        self.clientMessageID = clientMessageID; self.sender = sender; self.recipient = recipient
        self.text = text; self.expectedEpoch = expectedEpoch
    }
}

public struct MessageResponse: Sendable {
    public let clientMessageID: String
    public let sequence: Int
    public let acceptedAt: String
    public let serverEpoch: String
    public init(clientMessageID: String, sequence: Int, acceptedAt: String, serverEpoch: String) {
        self.clientMessageID = clientMessageID; self.sequence = sequence
        self.acceptedAt = acceptedAt; self.serverEpoch = serverEpoch
    }
}

public struct InboxResponse: Sendable {
    public let messages: [IncomingMessage]
    public let nextCursor: Int
    public let hasMore: Bool
    public init(messages: [IncomingMessage], nextCursor: Int, hasMore: Bool) {
        self.messages = messages; self.nextCursor = nextCursor; self.hasMore = hasMore
    }
}

// MARK: - Errors

public enum MessagingError: Error, Sendable {
    case invalidRequest(String)
    case conflict(String)
    case epochChanged(newEpoch: String)
    case invalidCursor(String)
    case networkError(String)
    case protocolError(String)
    case storageError(String)
}

// MARK: - Port protocols

public protocol ChatStore: AnyObject, Sendable {
    func loadIdentity() async throws -> String?
    func saveIdentity(_ username: String) async throws
    func enqueue(id: String, sender: String, recipient: String, text: String) async throws
    func pendingMessages() async throws -> [PendingMessage]
    func acknowledgeMessage(id: String, sequence: Int, acceptedAt: String) async throws
    func failMessage(id: String, code: String) async throws
    func commitPage(messages: [IncomingMessage], cursor: Int) async throws
    func snapshot(peer: String?) async throws -> ChatSnapshot
    func loadSyncState() async throws -> SyncStateRecord
    func updateEpoch(active: String?, pending: String?) async throws
    func resetSession(epoch: String) async throws
}

public protocol MessagingTransport: AnyObject, Sendable {
    func fetchMeta() async throws -> MetaResponse
    func submit(_ request: SubmitRequest) async throws -> MessageResponse
    func fetchInbox(username: String, after: Int, limit: Int, epoch: String) async throws -> InboxResponse
}
