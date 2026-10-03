pluginManagement {
    repositories {
        mavenCentral()
        gradlePluginPortal()
        google()
    }
}

dependencyResolutionManagement {
    repositories {
        mavenCentral()
        google()
    }
    // gradle/libs.versions.toml is auto-imported as the "libs" catalog by Gradle 8.x
}

rootProject.name = "messaging"
include(":messaging-core")
include(":messaging-http")
include(":messaging-storage")
include(":messaging-cli")
include(":android-app")
