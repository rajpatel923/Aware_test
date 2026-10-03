package com.example.messaging.app

import android.app.Application
import app.cash.sqldelight.driver.android.AndroidSqliteDriver
import com.example.messaging.core.MessagingClient
import com.example.messaging.http.OkHttpTransport
import com.example.messaging.storage.MessagingDatabase
import com.example.messaging.storage.SqlDelightStore

class MessagingApplication : Application() {

    lateinit var messagingClient: MessagingClient
        private set

    override fun onCreate() {
        super.onCreate()
        val serverUrl = "http://10.0.2.2:8000"
        val driver = AndroidSqliteDriver(MessagingDatabase.Schema, this, "messages.db")
        val store = SqlDelightStore(driver)
        val transport = OkHttpTransport(serverUrl)
        messagingClient = MessagingClient(store, transport, pageSize = 100)
    }
}
