plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
    application
}

kotlin {
    jvmToolchain(17)
}

application {
    mainClass.set("com.example.messaging.cli.MainKt")
}

dependencies {
    implementation(project(":messaging-core"))
    implementation(project(":messaging-http"))
    implementation(project(":messaging-storage"))
    implementation(libs.kotlinx.coroutines.core)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.sqldelight.jdbc.driver)
    implementation(libs.sqldelight.sqlite.driver)
}

tasks.jar {
    manifest { attributes["Main-Class"] = "com.example.messaging.cli.MainKt" }
    duplicatesStrategy = DuplicatesStrategy.EXCLUDE
    from(configurations.runtimeClasspath.get().map { if (it.isDirectory) it else zipTree(it) })
}
