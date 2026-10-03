package com.example.messaging.cli

import app.cash.sqldelight.driver.jdbc.sqlite.JdbcSqliteDriver
import com.example.messaging.core.*
import com.example.messaging.http.OkHttpTransport
import com.example.messaging.storage.SqlDelightStore
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import java.io.File

// MARK: - JSON Lines protocol

@Serializable
private data class CLIRequest(val id: String, val cmd: String, val args: JsonObject? = null)

// MARK: - I/O

private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

private fun emit(id: String, result: JsonElement) {
    val envelope = buildJsonObject {
        put("id", id)
        put("ok", true)
        put("result", result)
    }
    println(json.encodeToString(envelope))
    System.out.flush()
}

private fun emitError(id: String, code: String, message: String) {
    val envelope = buildJsonObject {
        put("id", id)
        put("ok", false)
        put("error", buildJsonObject {
            put("code", code)
            put("message", message)
        })
    }
    println(json.encodeToString(envelope))
    System.out.flush()
}

// MARK: - Dispatch

private suspend fun dispatch(id: String, cmd: String, args: JsonObject?, client: MessagingClient) {
    try {
        when (cmd) {
            "identify" -> {
                val name = args?.get("name")?.jsonPrimitive?.content ?: error("Missing arg: name")
                val username = client.identify(name)
                emit(id, buildJsonObject { put("username", username) })
            }
            "send" -> {
                val recipient = args?.get("recipient")?.jsonPrimitive?.content ?: error("Missing arg: recipient")
                val text = args?.get("text")?.jsonPrimitive?.content ?: error("Missing arg: text")
                val mid = client.enqueue(recipient, text)
                emit(id, buildJsonObject { put("client_message_id", mid); put("status", "queued") })
            }
            "offline" -> {
                val enabled = args?.get("enabled")?.jsonPrimitive?.boolean ?: error("Missing arg: enabled")
                client.setOffline(enabled)
                emit(id, buildJsonObject { put("offline", enabled) })
            }
            "fault" -> {
                val drop = args?.get("drop_next_response")?.jsonPrimitive?.content ?: error("Missing arg: drop_next_response")
                client.fault(drop)
                emit(id, buildJsonObject { put("armed", true) })
            }
            "sync_once" -> {
                val r = client.syncOnce()
                emit(id, buildJsonObject {
                    put("outcome", r.outcome)
                    put("accepted", r.accepted)
                    put("received", r.received)
                    put("pending", r.pending)
                })
            }
            "snapshot" -> {
                val peer = args?.get("peer")?.jsonPrimitive?.contentOrNull
                val snap = client.snapshot(peer)
                emit(id, buildJsonObject {
                    put("username", snap.username?.let { JsonPrimitive(it) } ?: JsonNull)
                    put("server_epoch", snap.serverEpoch?.let { JsonPrimitive(it) } ?: JsonNull)
                    put("cursor", snap.cursor)
                    put("sync_state", snap.syncState)
                    put("pending_count", snap.pendingCount)
                    put("messages", buildJsonArray {
                        for (m in snap.messages) add(buildJsonObject {
                            put("client_message_id", m.clientMessageId)
                            put("sender", m.sender)
                            put("recipient", m.recipient)
                            put("text", m.text)
                            put("status", m.status)
                            put("sequence", m.sequence?.let { JsonPrimitive(it) } ?: JsonNull)
                            put("error_code", m.errorCode?.let { JsonPrimitive(it) } ?: JsonNull)
                        })
                    })
                })
            }
            "reset_session" -> {
                val (epoch, cursor) = client.resetSession()
                emit(id, buildJsonObject { put("server_epoch", epoch); put("cursor", cursor) })
            }
            "shutdown" -> {
                emit(id, buildJsonObject {})
                System.exit(0)
            }
            else -> emitError(id, "UNKNOWN_COMMAND", "Unknown command: $cmd")
        }
    } catch (e: Exception) {
        if (e is kotlinx.coroutines.CancellationException) throw e
        emitError(id, "CLIENT_ERROR", e.message ?: e.toString())
    }
}

// MARK: - Entry point

fun main(rawArgs: Array<String>) {
    var urlStr: String? = null
    var dataDir: String? = null
    var pageSize = 100
    var i = 0
    while (i < rawArgs.size) {
        when (rawArgs[i]) {
            "--url"       -> { urlStr = rawArgs[++i] }
            "--data-dir"  -> { dataDir = rawArgs[++i] }
            "--page-size" -> { pageSize = rawArgs[++i].toIntOrNull() ?: 100 }
        }
        i++
    }

    val baseUrl = requireNotNull(urlStr) { "usage: --url <url> --data-dir <dir> [--page-size N]" }
    val dir = requireNotNull(dataDir) { "usage: --url <url> --data-dir <dir> [--page-size N]" }
    File(dir).mkdirs()

    val dbPath = "$dir/messages.db"
    val driver = JdbcSqliteDriver("jdbc:sqlite:$dbPath")
    com.example.messaging.storage.MessagingDatabase.Schema.create(driver)
    val store = SqlDelightStore(driver)
    val transport = OkHttpTransport(baseUrl)
    val client = MessagingClient(store, transport, pageSize)

    runBlocking {
        client.load()

        val stdin = System.`in`.bufferedReader()
        for (line in stdin.lineSequence()) {
            val trimmed = line.trim()
            if (trimmed.isEmpty()) continue
            val req = try {
                json.decodeFromString<CLIRequest>(trimmed)
            } catch (e: Exception) {
                emitError("?", "PARSE_ERROR", e.message ?: "parse error")
                continue
            }
            dispatch(req.id, req.cmd, req.args, client)
        }
    }
}
