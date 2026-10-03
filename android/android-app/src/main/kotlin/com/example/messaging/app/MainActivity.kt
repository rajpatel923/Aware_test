package com.example.messaging.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.viewmodel.compose.viewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as MessagingApplication
        setContent {
            MessagingTheme {
                val vm: MessagingViewModel = viewModel(
                    factory = MessagingViewModel.Factory(app.messagingClient)
                )
                MessagingApp(vm)
            }
        }
    }
}
