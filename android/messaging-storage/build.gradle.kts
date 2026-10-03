plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.sqldelight)
}

kotlin {
    jvmToolchain(17)
}

sqldelight {
    databases {
        create("MessagingDatabase") {
            packageName.set("com.example.messaging.storage")
            dialect("app.cash.sqldelight:sqlite-3-38-dialect:2.0.2")
        }
    }
}

dependencies {
    implementation(project(":messaging-core"))
    implementation(libs.sqldelight.runtime)
    implementation(libs.sqldelight.coroutines)
    testImplementation(libs.junit.jupiter)
    testImplementation(libs.sqldelight.sqlite.driver)
    testImplementation(libs.kotlinx.coroutines.test)
}

tasks.test { useJUnitPlatform() }
