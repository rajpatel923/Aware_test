# Platform: Android (Kotlin)

This file defines how the shared spec is realized on Android: language, libraries, structure, platform-specific pitfalls, and commands. It adds no behavior. Every behavioral rule comes from `domain.md`, `protocol.md`, `api.md`, `offline-behavior.md`, `ui.md`, and `test.md`. If this file seems to require behavior those files do not define, that is a spec bug: report it.

## 1. Toolchain

- Language: Kotlin with coroutines and Flow.
- App minimum: Android 8.0 (API 26). Target and compile SDK: latest stable at E01.
- Headless runner: JVM command-line application (macOS or Linux).
- JDK 17. Gradle via the Gradle wrapper only, never a system `gradle` in normal use.
- Exact versions are recorded in `.agents/TASKS.md` (E01).

K1.1 Libraries are limited to: Kotlin standard library, kotlinx.coroutines, kotlinx.serialization (JSON), **OkHttp**, **SQLDelight** (with its Android and JDBC SQLite drivers), Jetpack Compose, and AndroidX Lifecycle. No other dependency without a spec change. No Retrofit, Room, or DI framework.

K1.2 Use the latest stable versions that work together with the recorded JDK and Android Gradle Plugin. Pin every version in `gradle/libs.versions.toml`, and report them in the handoff.

K1.3 The Gradle wrapper (`gradlew`, `gradlew.bat`, `gradle/wrapper/`) is part of the generated output and is copied from a committed template in the generator. No locally installed `gradle` is required to regenerate the project; the wrapper resolves its Gradle distribution at build time from the version declared in `gradle/wrapper/gradle-wrapper.properties`. The template files are listed in `GENERATION_BOUNDARY.md`.

## 2. Structure

Generated output lives at `clients/android/`. One Gradle build with these modules:

| Module | Kind | Contains | May depend on |
|---|---|---|---|
| `:core` | Kotlin/JVM library | Domain, protocol, sync engine, ports (`Storage`, `Transport`, `Clock`, `IdSource`) | stdlib, coroutines |
| `:http` | Kotlin/JVM library | OkHttp transport, wire DTOs, error mapping | `:core`, OkHttp, kotlinx.serialization |
| `:store` | Kotlin/JVM library | SQLDelight schema, queries, transactions | `:core`, SQLDelight runtime (no concrete driver) |
| `:runner` | JVM application | Headless runner (`test.md` section 2); supplies `JdbcSqliteDriver` | all three libraries |
| `:app` | Android application | Compose UI, view models, app composition; supplies `AndroidSqliteDriver` | all three libraries, Android libraries |

K2.1 `:core` MUST NOT depend on Android classes, OkHttp, SQLDelight, or Compose. Only `:app` and `:runner` construct adapters.

K2.2 `:app` and `:runner` MUST use the same three libraries. Storage logic is identical for both drivers and never branches by platform.

## 3. Domain pitfalls

These are the places a straightforward Kotlin implementation breaks the shared rules.

K3.1 **Username lowercasing** (`domain.md` D1.1). Do not use `lowercase()`: it is Unicode-aware, so the Kelvin sign `K` (U+212A) becomes ASCII `k`, turning an invalid name into a valid one. Convert only `'A'..'Z'`, then validate.

K3.2 **Text length** (D4.1). Use `text.encodeToByteArray(throwOnInvalidSequence = true).size`. The default silently replaces lone surrogates with `?`, turning invalid text into valid text. Never use `text.length` (UTF-16 units).

K3.3 **No normalization** (D4.2). Never apply `java.text.Normalizer`; store and send text exactly as received.

K3.4 **Event IDs** (D3). `UUID.randomUUID().toString()` is already lowercase and hyphenated; use it as is.

K3.5 **Timestamps** (`api.md` section 2). Parse `accepted_at` with `java.time.Instant`; display only.

## 4. Concurrency

K4.1 A single application-scoped `MessagingClient` owns a structured `CoroutineScope` and the one sync job. Guard job ownership with a `Mutex` and a generation counter; ignore results from a superseded generation (`offline-behavior.md` O6.1, O6.3). Never use `GlobalScope`.

K4.2 Never hold the mutex or a database transaction across a network call (O6.2). Run blocking SQL on `Dispatchers.IO`.

K4.3 Always rethrow `CancellationException`; never classify it as a network failure (O4.3).

K4.4 State reaches the UI as a read-only `StateFlow` of immutable snapshots, collected with `collectAsStateWithLifecycle`. Composables never call storage or HTTP directly.

## 5. Storage

K5.1 SQLDelight in `:store`, used unchanged by both drivers. Database file in app-private storage (`Context.getDatabasePath`) for the app; in the `--data-dir` directory for the runner.

K5.2 Enable foreign keys explicitly on both drivers. Use SQLDelight migrations (`.sqm` files), append-only. A failed migration enters `storage_error` (O11.3); never delete the database.

K5.3 The transactions in `offline-behavior.md` O11.2 each run in one `transaction { }` block.

## 6. HTTP

K6.1 One shared `OkHttpClient` with `retryOnConnectionFailure(false)`, `callTimeout(10, SECONDS)`, and no cache configured. OkHttp's default retry would resend requests outside the outbox logic (`api.md` A5.2).

K6.2 kotlinx.serialization `Json` with `ignoreUnknownKeys = true` (responses, A1.6), `isLenient = false`, and `coerceInputValues = false`. Required fields have no default values, so missing fields fail decoding. Decoding success alone is not validation: then validate per `protocol.md` P5.5 and P7.3.

K6.3 URL-encode the username in the mailbox path with `HttpUrl.Builder.addPathSegment`.

## 7. App

K7.1 Jetpack Compose with one `ViewModel` per screen holding only transient UI state; view models receive the client from the application, and destroying one never stops the client.

K7.2 `ProcessLifecycleOwner` drives activity: started → active; stopped → inactive (O10.1–O10.3). No WorkManager or push notifications (O10.5).

K7.3 Server base URL comes from configuration. The emulator reaches the host machine at `10.0.2.2`, so the debug default is `http://10.0.2.2:8000`. A physical device needs the host's LAN address.

K7.4 Declare `INTERNET` permission. Allow cleartext HTTP only in the debug build, through a network security config limited to `10.0.2.2` and `localhost`. Never set `usesCleartextTraffic="true"` globally.

## 8. Headless runner

K8.1 Start-up: `runner --base-url <url> --data-dir <path>`. Manual mode is the default (`test.md` T2.5); `--auto` enables timers.

K8.2 Reads JSON Lines on stdin, writes one result line per request to stdout, flushing after each line. Logs go to stderr only.

K8.3 The `network` and `fault` commands are implemented by a transport wrapper in `:runner` around the real `:http` transport, never inside `:core` (T2.3, T2.4).

K8.4 The harness runs the installed distribution, not `gradlew run`, because Gradle does not forward stdin reliably.

## 9. Commands

All commands are **unverified** until run and recorded in `.agents/TASKS.md`. Working directory: the Android generated path.

| Purpose | Command |
|---|---|
| Unit tests | `./gradlew :core:test :http:test :store:test` |
| Build runner for the harness | `./gradlew :runner:installDist` |
| Run runner | `runner/build/install/runner/bin/runner --base-url <url> --data-dir <path>` |
| Build app | `./gradlew :app:assembleDebug` |
| Install on emulator | `adb install -r app/build/outputs/apk/debug/app-debug.apk` |

Once a command is verified, record the exact form here.