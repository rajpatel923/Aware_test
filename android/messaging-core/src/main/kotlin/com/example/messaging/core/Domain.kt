package com.example.messaging.core

// MARK: - Value types

data class Username(val value: String) {
    companion object {
        /** §2.1–2.2: trim ASCII whitespace, ASCII-only lowercase, validate [a-z0-9_]{1,32} */
        fun parse(raw: String): Username {
            var s = raw.trimAsciiWhitespace()
            // ASCII-only lowercase: never locale-aware
            s = buildString(s.length) {
                for (c in s) {
                    append(if (c in 'A'..'Z') c + ('a' - 'A') else c)
                }
            }
            require(s.isNotEmpty() && s.length <= 32 && s.all { it in 'a'..'z' || it in '0'..'9' || it == '_' }) {
                "Invalid username: $raw"
            }
            return Username(s)
        }

        private fun String.trimAsciiWhitespace(): String {
            var start = 0
            var end = length
            while (start < end && this[start].let { it == ' ' || it == '\t' || it == '\r' || it == '\n' }) start++
            while (end > start && this[end - 1].let { it == ' ' || it == '\t' || it == '\r' || it == '\n' }) end--
            return substring(start, end)
        }
    }

    override fun toString() = value
}

data class PendingMessage(
    val id: String,
    val sender: String,
    val recipient: String,
    val text: String,
)

data class IncomingMessage(
    val clientMessageId: String,
    val sender: String,
    val recipient: String,
    val text: String,
    val sequence: Long,
)

data class SyncStateRecord(
    val epoch: String? = null,
    val pendingEpoch: String? = null,
    val cursor: Long = 0L,
)

data class MessageSnapshot(
    val clientMessageId: String,
    val sender: String,
    val recipient: String,
    val text: String,
    val status: String,          // "queued" | "accepted" | "failed"
    val sequence: Long?,
    val errorCode: String?,
)

data class ChatSnapshot(
    val username: String?,
    val serverEpoch: String?,
    val cursor: Long,
    val syncState: String,       // "online" | "offline"
    val pendingCount: Int,
    val messages: List<MessageSnapshot>,
)

// MARK: - Transport I/O

data class MetaResponse(val serverEpoch: String)

data class SubmitRequest(
    val clientMessageId: String,
    val sender: String,
    val recipient: String,
    val text: String,
    val expectedEpoch: String,
)

data class MessageResponse(
    val clientMessageId: String,
    val sequence: Long,
    val acceptedAt: String,
    val serverEpoch: String,
)

data class InboxResponse(
    val messages: List<IncomingMessage>,
    val nextCursor: Long,
    val hasMore: Boolean,
)

// MARK: - Errors

sealed class MessagingError(message: String) : Exception(message) {
    class InvalidRequest(msg: String) : MessagingError(msg)
    class Conflict(val code: String) : MessagingError(code)
    class EpochChanged(val newEpoch: String) : MessagingError("SERVER_EPOCH_CHANGED: $newEpoch")
    class InvalidCursor(msg: String) : MessagingError(msg)
    class Network(msg: String) : MessagingError(msg)
    class Protocol(msg: String) : MessagingError(msg)
    class Storage(msg: String) : MessagingError(msg)
}

// MARK: - Ports

interface ChatStore {
    suspend fun loadIdentity(): String?
    suspend fun saveIdentity(username: String)
    suspend fun enqueue(id: String, sender: String, recipient: String, text: String)
    suspend fun pendingMessages(): List<PendingMessage>
    suspend fun acknowledgeMessage(id: String, sequence: Long, acceptedAt: String)
    suspend fun failMessage(id: String, code: String)
    suspend fun commitPage(messages: List<IncomingMessage>, cursor: Long)
    suspend fun snapshot(peer: String?): ChatSnapshot
    suspend fun loadSyncState(): SyncStateRecord
    suspend fun updateEpoch(active: String?, pending: String?)
    suspend fun resetSession(epoch: String)
}

interface MessagingTransport {
    suspend fun fetchMeta(): MetaResponse
    suspend fun submit(request: SubmitRequest): MessageResponse
    suspend fun fetchInbox(username: String, after: Long, limit: Int, epoch: String): InboxResponse
}
