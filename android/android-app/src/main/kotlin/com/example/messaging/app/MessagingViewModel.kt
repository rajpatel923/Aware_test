package com.example.messaging.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.messaging.core.MessagingClient
import com.example.messaging.core.MessageSnapshot
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

data class UiState(
    val username: String? = null,
    val messages: List<MessageSnapshot> = emptyList(),
    val pendingCount: Int = 0,
    val serverEpoch: String? = null,
    val syncState: String = "idle",
    val error: String? = null,
)

class MessagingViewModel(private val client: MessagingClient) : ViewModel() {

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    private var syncJob: Job? = null

    init {
        viewModelScope.launch {
            client.load()
            refreshSnapshot()
            startSyncLoop()
        }
    }

    fun identify(name: String) {
        viewModelScope.launch {
            runCatching { client.identify(name) }
                .onSuccess { refreshSnapshot() }
                .onFailure { _state.value = _state.value.copy(error = it.message) }
        }
    }

    fun send(recipient: String, text: String) {
        viewModelScope.launch {
            runCatching { client.enqueue(recipient, text) }
                .onSuccess { refreshSnapshot() }
                .onFailure { _state.value = _state.value.copy(error = it.message) }
        }
    }

    fun syncOnce() {
        viewModelScope.launch {
            runCatching { client.syncOnce() }
                .onSuccess { refreshSnapshot() }
                .onFailure { _state.value = _state.value.copy(error = it.message) }
        }
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }

    private fun startSyncLoop() {
        syncJob?.cancel()
        syncJob = viewModelScope.launch {
            while (isActive) {
                runCatching { client.syncOnce() }.onSuccess { refreshSnapshot() }
                delay(3_000)
            }
        }
    }

    private suspend fun refreshSnapshot() {
        val snap = runCatching { client.snapshot(null) }.getOrNull() ?: return
        _state.value = UiState(
            username = snap.username,
            messages = snap.messages,
            pendingCount = snap.pendingCount,
            serverEpoch = snap.serverEpoch,
            syncState = snap.syncState,
        )
    }

    override fun onCleared() {
        super.onCleared()
        syncJob?.cancel()
    }

    class Factory(private val client: MessagingClient) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T =
            MessagingViewModel(client) as T
    }
}
