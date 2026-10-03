package com.example.messaging.http

import com.example.messaging.core.*
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.net.URLEncoder
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

// MARK: - Wire DTOs

@Serializable
private data class MetaDTO(
    val protocol_version: String,
    val server_epoch: String,
)

@Serializable
private data class SubmitBodyDTO(
    val client_message_id: String,
    val sender: String,
    val recipient: String,
    val text: String,
)

@Serializable
private data class MessageDTO(
    val client_message_id: String,
    val sender: String,
    val recipient: String,
    val text: String,
    val sequence: Long,
    val accepted_at: String,
    val server_epoch: String,
)

@Serializable
private data class InboxPageDTO(
    val messages: List<MessageDTO>,
    val next_cursor: Long,
    val has_more: Boolean,
    val server_epoch: String,
)

@Serializable
private data class ErrorDTO(
    val code: String,
    val message: String,
    val server_epoch: String? = null,
)

// MARK: - Transport

class OkHttpTransport(private val baseUrl: String) : MessagingTransport {
    private val json = Json { ignoreUnknownKeys = true }
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()
    private val jsonType = "application/json; charset=utf-8".toMediaType()

    private fun url(path: String) = "${baseUrl.trimEnd('/')}$path"

    private suspend fun <T> execute(request: Request, decode: (String, Int) -> T): T = withContext(Dispatchers.IO) {
        val resp = try {
            client.newCall(request).execute()
        } catch (e: IOException) {
            throw MessagingError.Network(e.message ?: "IO error")
        }
        val body = resp.body?.string() ?: ""
        decode(body, resp.code)
    }

    private fun mapError(body: String, status: Int): Nothing {
        val err = try { json.decodeFromString<ErrorDTO>(body) } catch (_: Exception) {
            throw MessagingError.Network("HTTP $status")
        }
        when {
            err.code == "SERVER_EPOCH_CHANGED" -> throw MessagingError.EpochChanged(err.server_epoch ?: "")
            err.code == "MESSAGE_ID_CONFLICT" -> throw MessagingError.Conflict(err.code)
            status == 422 || status == 409 -> throw MessagingError.InvalidRequest(err.message)
            else -> throw MessagingError.Network("HTTP $status: ${err.message}")
        }
    }

    override suspend fun fetchMeta(): MetaResponse {
        val req = Request.Builder().url(url("/v1/meta")).get().build()
        return execute(req) { body, status ->
            if (status != 200) mapError(body, status)
            val dto = json.decodeFromString<MetaDTO>(body)
            MetaResponse(dto.server_epoch)
        }
    }

    override suspend fun submit(request: SubmitRequest): MessageResponse {
        val bodyDto = SubmitBodyDTO(request.clientMessageId, request.sender, request.recipient, request.text)
        val reqBody = json.encodeToString(bodyDto).toRequestBody(jsonType)
        val req = Request.Builder()
            .url(url("/v1/messages"))
            .post(reqBody)
            .header("X-Server-Epoch", request.expectedEpoch)
            .build()
        return execute(req) { body, status ->
            if (status != 200) mapError(body, status)
            val dto = json.decodeFromString<MessageDTO>(body)
            MessageResponse(dto.client_message_id, dto.sequence, dto.accepted_at, dto.server_epoch)
        }
    }

    override suspend fun fetchInbox(username: String, after: Long, limit: Int, epoch: String): InboxResponse {
        val encoded = URLEncoder.encode(username, "UTF-8")
        val req = Request.Builder()
            .url(url("/v1/inbox/$encoded?after=$after&limit=$limit"))
            .get()
            .header("X-Server-Epoch", epoch)
            .header("Cache-Control", "no-store")
            .build()
        return execute(req) { body, status ->
            if (status != 200) mapError(body, status)
            val dto = json.decodeFromString<InboxPageDTO>(body)
            val msgs = dto.messages.map { m ->
                IncomingMessage(m.client_message_id, m.sender, m.recipient, m.text, m.sequence)
            }
            InboxResponse(msgs, dto.next_cursor, dto.has_more)
        }
    }
}
