# android/AGENTS.md

Rules for work under `android/`. These refine root `AGENTS.md`; read both. Paths are relative to the repository root.

## Scope

The Kotlin client: one messaging core shared by a Jetpack Compose app and a headless JVM runner. Tasks A02 (core, adapters, runner) and N02 (native app) in `.agent/task.md`. Nothing below exists yet; do not create files just because they are listed here.

Before writing behavior, read `spec/behavior.md`, `spec/protocol.openapi.yaml`, `spec/scenarios/`, and design sections 3–5, 7, 9, and 10. The spec wins over this file and the design. If the spec is missing or ambiguous, report it and continue only independent work. Never copy or translate Swift code; both clients implement the spec independently.

## Commands

Always use the Gradle wrapper (`./gradlew`), never a system Gradle. `ANDROID_HOME` must be set for Android modules.

| Purpose | Command | Working dir | Status |
|---|---|---|---|
| Build all JVM modules | `./gradlew :messaging-core:build :messaging-http:build :messaging-storage:build :messaging-cli:build --no-daemon` | `android/` | PASS |
| Build headless CLI jar | `./gradlew :messaging-cli:jar --no-daemon` | `android/` | PASS |
| Run headless CLI | `java -jar messaging-cli/build/libs/messaging-cli.jar --url http://127.0.0.1:8000 --data-dir <dir>` | `android/` | PASS |
| Kotlin acceptance tests | `python -m pytest test_kotlin_client.py -v` | `tests/` | PASS (7/7) |
| Build Android app (debug) | `ANDROID_HOME=~/Library/Android/sdk ./gradlew :android-app:assembleDebug --no-daemon` | `android/` | PASS |
| Install APK on emulator | `adb install android-app/build/outputs/apk/debug/android-app-debug.apk` | `android/` | PASS |
| Launch app on emulator | `adb shell am start -n com.example.messaging.app/.MainActivity` | any | PASS |

## Ownership

Android tasks own `android/` only. Never edit `spec/`, `tests/`, `backend/`, `ios/`, root instructions, or `.agent/task.md`; propose changes in the handoff. Never fix a client bug by weakening a shared expected result.

## Layout

- `android/settings.gradle.kts`: module list; Gradle wrapper and version catalog alongside.
- `:messaging-core`: domain, `MessagingClient` facade, sync coordinator, ports, snapshots. Kotlin, coroutines, and Flow only; no Android classes.
- `:messaging-http`: OkHttp transport, kotlinx.serialization DTOs, error mapping.
- `:messaging-storage`: SQLDelight schema, queries, migrations, transactional store. Depends on the SQLDelight runtime only, never a concrete driver.
- `:messaging-cli`: JVM headless runner; supplies `JdbcSqliteDriver`.
- `:android-app`: Compose screens, ViewModels, `AppContainer`, lifecycle bridge; supplies `AndroidSqliteDriver`.

Dependencies point inward. Storage logic never branches by platform. Unit and adapter tests live in each module; cross-client tests stay in `tests/`. Do not create empty modules or files to match this list.

## Core and concurrency

An application-scoped `MessagingClient` owns a structured `CoroutineScope` (with a supervisor where independent failures should not cancel everything) and the single sync job. Guard task ownership and sync state with a `Mutex` or a serialized coordinator, plus a generation token so stale completions are discarded. `requestSync()` wakes the existing job; `syncOnce()` and automatic sync share one gate.

Expose a private `MutableStateFlow` only as read-only `StateFlow`, with no mutable collections in snapshots. Never use `GlobalScope`. Never hold the mutex or a database transaction across an HTTP call. Always rethrow `CancellationException`; never treat it as a network error. Run blocking SQL on `Dispatchers.IO`.

## HTTP adapter

OkHttp with kotlinx.serialization; DTOs stay in this module and the core model carries no serialization annotations. Build URLs from an injected base URL with encoded usernames, set the 10 s timeouts and `X-Server-Epoch` header, and map statuses per the error table. Configure JSON to ignore unknown keys but require mandatory fields. Disable caching for inbox GETs. Validate epoch, IDs, recipient, payload, sequence order, and cursor before returning values to the core. Any retry must resend the identical ID and body.

## Storage adapter

SQLDelight in `:messaging-storage`, used unchanged by both drivers. Enable foreign keys, use versioned migrations, and fail visibly on migration error; never delete the database to recover. Implement the enqueue, acceptance, and receive transactions exactly as in design section 7. Observe changes through Flow, never by querying on recomposition. A conflicting incoming duplicate is a protocol error, never an overwrite.

Measure text limits in UTF-8 bytes (`text.encodeToByteArray().size`), never `String.length`. Canonicalize usernames with ASCII-only rules, never `lowercase()` with a default locale.

## Compose app

`AppContainer` uses `Context` only to resolve the database file and build `AndroidSqliteDriver`, then builds the store, transport, clock, ID source, and one client. ViewModel factories receive the client. No DI framework required; no Activity references held by the core or store.

ViewModels expose `StateFlow<ChatUiState>`, collected with `collectAsStateWithLifecycle`, and use `viewModelScope` only for observation and UI requests. Destroying a ViewModel never cancels the client or queue. Only route-level composables see the ViewModel; rows, composer, and banner take plain state and callbacks. List keys are logical message keys, never positions. Composables never open the database, call HTTP, or generate IDs.

On Send: clear the draft only after the enqueue commits, keeping any text typed meanwhile. On storage failure, keep the draft and show the error. Statuses: Queued, Sending, Accepted by server, Failed. No delivered or read marks.

Lifecycle: a process-level lifecycle observer activates the client on foreground and pauses on background. Activity recreation reuses the same client. After process death, rebuild from SQLite. No WorkManager or FCM in v1. Inject the server base URL (the emulator reaches the host at `10.0.2.2`); allow cleartext HTTP only in a debug network security config.

## Headless runner

Uses the same core, HTTP, and storage modules as the app, with no Android classes or fake messaging logic. Implements the JSONL contract in design section 10: one result per request ID on stdout, logs on stderr. Each instance takes its own data directory and base URL; restarting with the same directory reloads queued messages. A fault-injection transport may wrap the real HTTP adapter. Runs on macOS or Linux.

## Required checks

A02 is done when each has a recorded passing result using the JDBC driver and the real server: the seven client guarantees listed under A01/A02 in `.agent/task.md`. N02 is done when the app builds and runs on the recorded emulator or device using `AndroidSqliteDriver` and completes identify, send, receive, queue offline, resume and flush, and relaunch with persisted state, with only one sync loop after resume and a responsive UI.

A JVM pass proves nothing about the Android driver or app. A missing Android SDK or emulator makes N02 `blocked`, never `done`. Screenshots alone do not prove persistence.

## AGENTS.md files

Any new subdirectory or Gradle module added under `android/` must include its own `AGENTS.md` that:
- References this file and root `AGENTS.md` as parents.
- Describes the module's scope, dependencies, and build/test commands.
- Lists verified commands with working directory and exit status once they pass.

Update this file whenever a task changes the layout, module list, or conventions for `android/`.

## Done

Pin all versions in the version catalog, including the JVM target, and commit the Gradle wrapper. The project must build from the repository with no unrecorded IDE setup. Review the diff, confirm only `android/` changed, commit coherent increments, and hand off per root `AGENTS.md`.