import Foundation
import GRDB
import MessagingCore

public final class GRDBStore: ChatStore {
    private let db: DatabaseQueue

    public init(path: String) throws {
        var config = Configuration()
        config.foreignKeysEnabled = true
        db = try DatabaseQueue(path: path, configuration: config)
        try migrate()
    }

    // MARK: - Schema

    private func migrate() throws {
        var migrator = DatabaseMigrator()
        migrator.registerMigration("v1") { db in
            try db.execute(sql: """
                CREATE TABLE IF NOT EXISTS identity (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    username TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    client_message_id TEXT PRIMARY KEY,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    sequence INTEGER,
                    accepted_at TEXT,
                    error_code TEXT
                );
                CREATE TABLE IF NOT EXISTS sync_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    epoch TEXT,
                    pending_epoch TEXT,
                    cursor INTEGER NOT NULL DEFAULT 0
                );
                INSERT OR IGNORE INTO sync_state (id, cursor) VALUES (1, 0);
            """)
        }
        try migrator.migrate(db)
    }

    // MARK: - Identity

    public func loadIdentity() async throws -> String? {
        try await db.read { db in
            let row = try Row.fetchOne(db, sql: "SELECT username FROM identity WHERE id = 1")
            return row.map { $0["username"] as String }
        }
    }

    public func saveIdentity(_ username: String) async throws {
        try await db.write { db in
            try db.execute(
                sql: "INSERT INTO identity (id, username) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET username = excluded.username",
                arguments: [username]
            )
        }
    }

    // MARK: - Outbox

    public func enqueue(id: String, sender: String, recipient: String, text: String) async throws {
        try await db.write { db in
            try db.execute(
                sql: "INSERT INTO messages (client_message_id, sender, recipient, text, status) VALUES (?, ?, ?, ?, 'queued')",
                arguments: [id, sender, recipient, text]
            )
        }
    }

    public func pendingMessages() async throws -> [PendingMessage] {
        try await db.read { db in
            try Row.fetchAll(db, sql: "SELECT client_message_id, sender, recipient, text FROM messages WHERE status = 'queued' ORDER BY rowid")
                .map { PendingMessage(id: $0["client_message_id"], sender: $0["sender"], recipient: $0["recipient"], text: $0["text"]) }
        }
    }

    public func acknowledgeMessage(id: String, sequence: Int, acceptedAt: String) async throws {
        try await db.write { db in
            try db.execute(
                sql: "UPDATE messages SET status = 'accepted', sequence = ?, accepted_at = ? WHERE client_message_id = ? AND status = 'queued'",
                arguments: [sequence, acceptedAt, id]
            )
        }
    }

    public func failMessage(id: String, code: String) async throws {
        try await db.write { db in
            try db.execute(
                sql: "UPDATE messages SET status = 'failed', error_code = ? WHERE client_message_id = ? AND status = 'queued'",
                arguments: [code, id]
            )
        }
    }

    // MARK: - Inbox

    public func commitPage(messages: [IncomingMessage], cursor: Int) async throws {
        try await db.write { db in
            for msg in messages {
                let existing = try Row.fetchOne(
                    db,
                    sql: "SELECT status FROM messages WHERE client_message_id = ?",
                    arguments: [msg.clientMessageID]
                )
                if let row = existing {
                    let status = row["status"] as String
                    if status == "queued" {
                        // §7.4: self-sent message arrives in inbox → mark accepted
                        try db.execute(
                            sql: "UPDATE messages SET status = 'accepted', sequence = ? WHERE client_message_id = ? AND status = 'queued'",
                            arguments: [msg.sequence, msg.clientMessageID]
                        )
                    }
                    // already accepted or failed: no-op
                } else {
                    try db.execute(
                        sql: "INSERT INTO messages (client_message_id, sender, recipient, text, status, sequence) VALUES (?, ?, ?, ?, 'accepted', ?)",
                        arguments: [msg.clientMessageID, msg.sender, msg.recipient, msg.text, msg.sequence]
                    )
                }
            }
            try db.execute(sql: "UPDATE sync_state SET cursor = ? WHERE id = 1", arguments: [cursor])
        }
    }

    // MARK: - Snapshot

    public func snapshot(peer: String?) async throws -> ChatSnapshot {
        try await db.read { db in
            let username = (try Row.fetchOne(db, sql: "SELECT username FROM identity WHERE id = 1")).map { $0["username"] as String }
            let stateRow = try Row.fetchOne(db, sql: "SELECT epoch, cursor FROM sync_state WHERE id = 1")
            let epoch: String? = stateRow.flatMap { $0["epoch"] }
            let cursor: Int = stateRow.map { $0["cursor"] } ?? 0

            let sql: String
            let args: StatementArguments
            if let p = peer {
                sql = "SELECT * FROM messages WHERE sender = ? OR recipient = ? ORDER BY COALESCE(sequence, 9999999999), rowid"
                args = [p, p]
            } else {
                sql = "SELECT * FROM messages ORDER BY COALESCE(sequence, 9999999999), rowid"
                args = []
            }
            let rows = try Row.fetchAll(db, sql: sql, arguments: args)
            let messages = rows.map { row -> MessageSnapshot in
                MessageSnapshot(
                    clientMessageID: row["client_message_id"],
                    sender: row["sender"],
                    recipient: row["recipient"],
                    text: row["text"],
                    status: row["status"],
                    sequence: row["sequence"],
                    errorCode: row["error_code"]
                )
            }
            let pendingCount = messages.filter { $0.status == "queued" }.count

            return ChatSnapshot(
                username: username,
                serverEpoch: epoch,
                cursor: cursor,
                syncState: "online",    // caller overrides this
                pendingCount: pendingCount,
                messages: messages
            )
        }
    }

    // MARK: - Sync state

    public func loadSyncState() async throws -> SyncStateRecord {
        try await db.read { db in
            guard let row = try Row.fetchOne(db, sql: "SELECT epoch, pending_epoch, cursor FROM sync_state WHERE id = 1") else {
                return SyncStateRecord()
            }
            return SyncStateRecord(
                epoch: row["epoch"],
                pendingEpoch: row["pending_epoch"],
                cursor: row["cursor"] ?? 0
            )
        }
    }

    public func updateEpoch(active: String?, pending: String?) async throws {
        try await db.write { db in
            try db.execute(
                sql: "UPDATE sync_state SET epoch = ?, pending_epoch = ? WHERE id = 1",
                arguments: [active, pending]
            )
        }
    }

    public func resetSession(epoch: String) async throws {
        try await db.write { db in
            try db.execute(
                sql: "UPDATE sync_state SET epoch = ?, pending_epoch = NULL, cursor = 0 WHERE id = 1",
                arguments: [epoch]
            )
        }
    }
}
