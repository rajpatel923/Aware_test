package com.example.messaging.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.messaging.core.MessageSnapshot

@Composable
fun MessagingTheme(content: @Composable () -> Unit) {
    MaterialTheme(content = content)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MessagingApp(vm: MessagingViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()

    if (state.username == null) {
        IdentifyScreen(onIdentify = { vm.identify(it) })
    } else {
        ConversationScreen(state = state, vm = vm)
    }

    state.error?.let { msg ->
        AlertDialog(
            onDismissRequest = { vm.clearError() },
            confirmButton = { TextButton(onClick = { vm.clearError() }) { Text("OK") } },
            title = { Text("Error") },
            text = { Text(msg) },
        )
    }
}

@Composable
fun IdentifyScreen(onIdentify: (String) -> Unit) {
    var name by remember { mutableStateOf("") }
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Messaging", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            label = { Text("Your name") },
            singleLine = true,
        )
        Spacer(Modifier.height(16.dp))
        Button(
            onClick = { if (name.isNotBlank()) onIdentify(name.trim()) },
            enabled = name.isNotBlank(),
        ) {
            Text("Continue")
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationScreen(state: UiState, vm: MessagingViewModel) {
    var recipient by remember { mutableStateOf("") }
    var messageText by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    LaunchedEffect(state.messages.size) {
        if (state.messages.isNotEmpty()) {
            listState.animateScrollToItem(state.messages.size - 1)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(state.username ?: "", fontWeight = FontWeight.Bold)
                        Text(
                            "pending: ${state.pendingCount}  sync: ${state.syncState}",
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                },
                actions = {
                    TextButton(onClick = { vm.syncOnce() }) { Text("Sync") }
                },
            )
        },
        bottomBar = {
            Surface(tonalElevation = 2.dp) {
                Column(Modifier.padding(8.dp)) {
                    OutlinedTextField(
                        value = recipient,
                        onValueChange = { recipient = it },
                        label = { Text("To") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(4.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        OutlinedTextField(
                            value = messageText,
                            onValueChange = { messageText = it },
                            label = { Text("Message") },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                        )
                        Spacer(Modifier.width(8.dp))
                        Button(
                            onClick = {
                                vm.send(recipient.trim(), messageText.trim())
                                messageText = ""
                            },
                            enabled = recipient.isNotBlank() && messageText.isNotBlank(),
                        ) {
                            Text("Send")
                        }
                    }
                }
            }
        },
    ) { padding ->
        LazyColumn(
            state = listState,
            contentPadding = PaddingValues(8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            items(state.messages) { msg ->
                MessageRow(msg = msg, me = state.username ?: "")
            }
        }
    }
}

@Composable
fun MessageRow(msg: MessageSnapshot, me: String) {
    val isMine = msg.sender == me
    val align = if (isMine) Alignment.End else Alignment.Start
    val color = if (isMine) MaterialTheme.colorScheme.primaryContainer
    else MaterialTheme.colorScheme.secondaryContainer

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = align,
    ) {
        Surface(color = color, shape = MaterialTheme.shapes.medium) {
            Column(Modifier.padding(horizontal = 12.dp, vertical = 6.dp)) {
                if (!isMine) {
                    Text(msg.sender, style = MaterialTheme.typography.labelSmall)
                }
                Text(msg.text)
                Text(
                    msg.status + if (msg.errorCode != null) " (${msg.errorCode})" else "",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
