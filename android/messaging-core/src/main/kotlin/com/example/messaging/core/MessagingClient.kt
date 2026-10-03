package com.example.messaging.core

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Application-scoped client facade. State is protected by a Mutex so all callers
 * share one in-memory state without races.
 */
class MessagingClient(
    private val store: ChatStore,
    private val transport: MessagingTransport,
    private val pageSize: Int = 100,
) {
    private val mutex = Mutex()
    private var syncState = SyncStateRecord()
    private var username: String? = null
    private var offline = false
    private var faultDropNext: String? = null

    /** Call once after construction to restore persisted state. */
    suspend fun load() = mutex.withLock {
        username = store.loadIdentity()
        syncState = store.loadSyncState()
    }

    // MARK: - Commands

    suspend fun identify(name: String): String = mutex.withLock {
        val u = Username.parse(name)
        store.saveIdentity(u.value)
        username = u.value
        u.value
    }

    suspend fun enqueue(recipient: String, text: String): String = mutex.withLock {
        val r = Username.parse(recipient)
        require(text.isNotEmpty() && text.encodeToByteArray().size <= 4096) {
            "Text must be 1–4096 UTF-8 bytes"
        }
        val sender = requireNotNull(username) { "Not identified" }
        val mid = java.util.UUID.randomUUID().toString().lowercase()
        store.enqueue(id = mid, sender = sender, recipient = r.value, text = text)
        mid
    }

    suspend fun setOffline(enabled: Boolean) = mutex.withLock { offline = enabled }

    suspend fun fault(drop: String) = mutex.withLock { faultDropNext = drop }

    data class SyncResult(val outcome: String, val accepted: Int, val received: Int, val pending: Int)

    suspend fun syncOnce(): SyncResult = mutex.withLock {
        if (offline) {
            val pending = store.pendingMessages().size
            return SyncResult("paused", 0, 0, pending)
        }

        // §10.2: adopt epoch from meta if absent
        if (syncState.epoch == null) {
            return try {
                val meta = transport.fetchMeta()
                syncState = syncState.copy(epoch = meta.serverEpoch)
                store.updateEpoch(active = meta.serverEpoch, pending = null)
                syncOnceInner()
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                SyncResult("backoff", 0, 0, store.pendingMessages().size)
            }
        }

        syncOnceInner()
    }

    /** Called with the mutex already held and epoch guaranteed non-null. */
    private suspend fun syncOnceInner(): SyncResult {
        val epoch = syncState.epoch!!
        var accepted = 0
        var received = 0

        // §11.2: inbox first, then outbox
        val uname = username
        if (uname != null) {
            var fetchMore = true
            while (fetchMore) {
                val resp = try {
                    transport.fetchInbox(uname, syncState.cursor, pageSize, epoch)
                } catch (e: MessagingError.EpochChanged) {
                    syncState = syncState.copy(pendingEpoch = e.newEpoch)
                    store.updateEpoch(active = syncState.epoch, pending = e.newEpoch)
                    return SyncResult("server_reset", accepted, received, store.pendingMessages().size)
                } catch (e: Exception) {
                    if (e is kotlinx.coroutines.CancellationException) throw e
                    return SyncResult("backoff", accepted, received, store.pendingMessages().size)
                }

                // Fault injection after response received
                if (faultDropNext == "inbox") {
                    faultDropNext = null
                    return SyncResult("backoff", accepted, received, store.pendingMessages().size)
                }

                // §7.2: validate page
                if (resp.messages.isEmpty() && resp.hasMore)
                    throw MessagingError.Protocol("Empty page claims has_more")

                if (resp.messages.isNotEmpty()) {
                    var prevSeq = syncState.cursor
                    for (msg in resp.messages) {
                        if (msg.sequence <= prevSeq) throw MessagingError.Protocol("Sequences not strictly increasing")
                        prevSeq = msg.sequence
                    }
                    val beforeCount = store.snapshot(null).messages.count { it.status == "accepted" }
                    store.commitPage(resp.messages, resp.nextCursor)
                    val afterCount = store.snapshot(null).messages.count { it.status == "accepted" }
                    received += maxOf(0, afterCount - beforeCount)
                    syncState = syncState.copy(cursor = resp.nextCursor)
                }

                fetchMore = resp.hasMore
            }
        }

        // Submit outbox (up to 10 per §11.2)
        val pending = store.pendingMessages()
        for (msg in pending.take(10)) {
            try {
                val resp = transport.submit(
                    SubmitRequest(msg.id, msg.sender, msg.recipient, msg.text, epoch)
                )

                // Fault injection after response received
                if (faultDropNext == "submit") {
                    faultDropNext = null
                    return SyncResult("backoff", accepted, received, store.pendingMessages().size)
                }

                store.acknowledgeMessage(msg.id, resp.sequence, resp.acceptedAt)
                accepted++
            } catch (e: MessagingError.EpochChanged) {
                syncState = syncState.copy(pendingEpoch = e.newEpoch)
                store.updateEpoch(active = syncState.epoch, pending = e.newEpoch)
                return SyncResult("server_reset", accepted, received, store.pendingMessages().size)
            } catch (e: MessagingError.Conflict) {
                store.failMessage(msg.id, e.code)
                continue
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                return SyncResult("backoff", accepted, received, store.pendingMessages().size)
            }
        }

        return SyncResult("ok", accepted, received, store.pendingMessages().size)
    }

    suspend fun snapshot(peer: String?): ChatSnapshot = mutex.withLock {
        val snap = store.snapshot(peer)
        snap.copy(syncState = if (offline) "offline" else "online")
    }

    suspend fun resetSession(): Pair<String, Long> = mutex.withLock {
        val newEpoch = syncState.pendingEpoch ?: transport.fetchMeta().serverEpoch
        syncState = SyncStateRecord(epoch = newEpoch, pendingEpoch = null, cursor = 0L)
        store.resetSession(newEpoch)
        Pair(newEpoch, 0L)
    }
}
