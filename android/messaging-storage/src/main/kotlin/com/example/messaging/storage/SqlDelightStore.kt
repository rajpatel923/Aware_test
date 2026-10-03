package com.example.messaging.storage

import app.cash.sqldelight.db.SqlDriver
import com.example.messaging.core.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class SqlDelightStore(driver: SqlDriver) : ChatStore {
    private val db = MessagingDatabase(driver)

    private suspend fun <T> io(block: suspend () -> T): T = withContext(Dispatchers.IO) { block() }

    // MARK: - Identity

    override suspend fun loadIdentity(): String? = io {
        db.messagingQueries.loadIdentity().executeAsOneOrNull()
    }

    override suspend fun saveIdentity(username: String) = io {
        db.messagingQueries.saveIdentity(username)
    }

    // MARK: - Outbox

    override suspend fun enqueue(id: String, sender: String, recipient: String, text: String) = io {
        db.messagingQueries.insertQueued(id, sender, recipient, text)
    }

    override suspend fun pendingMessages(): List<PendingMessage> = io {
        db.messagingQueries.pendingMessages().executeAsList().map {
            PendingMessage(it.client_message_id, it.sender, it.recipient, it.text)
        }
    }

    override suspend fun acknowledgeMessage(id: String, sequence: Long, acceptedAt: String) = io {
        db.messagingQueries.acknowledgeMessage(sequence, acceptedAt, id)
    }

    override suspend fun failMessage(id: String, code: String) = io {
        db.messagingQueries.failMessage(code, id)
    }

    // MARK: - Inbox — §7.3: atomic transaction

    override suspend fun commitPage(messages: List<IncomingMessage>, cursor: Long) = io {
        db.messagingQueries.transaction {
            for (msg in messages) {
                val existing = db.messagingQueries.messageByIdAndStatus(msg.clientMessageId).executeAsOneOrNull()
                when {
                    existing == null -> db.messagingQueries.insertAccepted(
                        msg.clientMessageId, msg.sender, msg.recipient, msg.text, msg.sequence
                    )
                    existing == "queued" -> db.messagingQueries.acceptQueuedByInbox(msg.sequence, msg.clientMessageId)
                    // already accepted or failed: no-op
                }
            }
            db.messagingQueries.updateCursor(cursor)
        }
    }

    // MARK: - Snapshot

    override suspend fun snapshot(peer: String?): ChatSnapshot = io {
        val username = db.messagingQueries.loadIdentity().executeAsOneOrNull()
        val state = db.messagingQueries.loadSyncState().executeAsOneOrNull()

        val messages: List<MessageSnapshot>
        if (peer != null) {
            messages = db.messagingQueries.messagesByPeer(peer, peer).executeAsList().map { row ->
                MessageSnapshot(row.client_message_id, row.sender, row.recipient, row.text,
                    row.status, row.sequence, row.error_code)
            }
        } else {
            messages = db.messagingQueries.allMessages().executeAsList().map { row ->
                MessageSnapshot(row.client_message_id, row.sender, row.recipient, row.text,
                    row.status, row.sequence, row.error_code)
            }
        }
        val pendingCount = messages.count { it.status == "queued" }
        ChatSnapshot(
            username = username,
            serverEpoch = state?.epoch,
            cursor = state?.cursor ?: 0L,
            syncState = "online",
            pendingCount = pendingCount,
            messages = messages,
        )
    }

    // MARK: - Sync state

    override suspend fun loadSyncState(): SyncStateRecord = io {
        val row = db.messagingQueries.loadSyncState().executeAsOneOrNull()
            ?: return@io SyncStateRecord()
        SyncStateRecord(
            epoch = row.epoch,
            pendingEpoch = row.pending_epoch,
            cursor = row.cursor,
        )
    }

    override suspend fun updateEpoch(active: String?, pending: String?) = io {
        db.messagingQueries.updateEpoch(active, pending)
    }

    override suspend fun resetSession(epoch: String) = io {
        db.messagingQueries.resetSession(epoch)
    }
}
