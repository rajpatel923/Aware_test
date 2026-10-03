# Design: Local Messaging App

Baseline v0.3. Path: `.agent/design.md`.

This document records the planned architecture and its reasons. Nothing here claims code, builds, or tests exist. Once `spec/` exists it is authoritative for behavior and wire format; keep this document aligned with it, and treat any conflict as a reviewable change, never as permission to change expected results to match broken code. Concrete values (limits, timings, error codes) are proposed defaults for `spec/`, not measurements.

## 1. Overview

One Python FastAPI server and two independent clients implementing the same rules. Swift: one messaging core used by a SwiftUI app and a headless runner. Kotlin: one messaging core used by a Compose app and a headless JVM runner. Clients persist their local state in SQLite; the server keeps mailboxes in memory; HTTP/JSON connects them. Swift and Kotlin share no messaging code, only the spec, wire schemas, and test scenarios.

## 2. Scope

v1 supports one saved username per client data directory, direct text messages through one server, offline reading and queuing, and preservation of queued messages and receive position across client restarts. The server detects its own restarts but does not persist data. Headless runners exercise the real core without UI. Mobile apps sync only while in the foreground. The server is a local, unauthenticated demo: names identify mailboxes but prove nothing, and records live until the process exits. The UI is an identify screen and a conversation screen.

Out of scope: multiple devices per username, attachments, reactions, groups, editing, read receipts, encryption, and push notifications. Do not build a plug-in system for them.

## 3. Protocol rules

| Item | Rule |
|---|---|
| Username | Trim ASCII space/tab/CR/LF, lowercase A–Z, then 1–32 chars of `[a-z0-9_]`. Canonical name = mailbox ID. No registration needed. |
| Text | Preserved exactly; valid Unicode, 1–4096 UTF-8 bytes; whitespace-only allowed |
| Message ID | Lowercase UUID v4, created once before enqueue |
| Logical key | `(sender, client_message_id)` within one server session |
| Sequence | Positive 64-bit server counter across all messages in a session; defines inbox order |
| Time | Server UTC, ISO 8601 with ms; display only, never for ordering |
| Page size | Default and max 100 |
| Poll interval | 1 s after an idle cycle, foreground only |
| Request deadline | 10 s per HTTP call |
| Backoff | 1, 2, 4, 8, 16, then 30 s; reset after a successful cycle |
| Concurrency | One POST in flight and one sync cycle per client |

The server validates authoritatively; clients apply the same rules for early feedback and never add their own limits or normalization. The text limit is in UTF-8 bytes because Swift and Kotlin count string length differently. Shared fixtures must cover emoji, accents, empty, and whitespace-only text.

## 4. HTTP API

- `GET /v1/meta` returns `protocol_version` and `server_epoch`.
- `POST /v1/messages` takes `client_message_id`, `sender`, `recipient`, `text` and returns those plus `sequence`, `accepted_at`, `server_epoch`. A first acceptance and an exact retry both return 200 with identical content.
- `GET /v1/inbox/{username}?after=&limit=` returns `messages`, `next_cursor`, `has_more`, `server_epoch`.

The epoch is generated at server startup and identifies the server instance. Every POST and inbox GET sends `X-Server-Epoch`; missing is malformed, mismatched returns a reset error.

`after` is exclusive. The server filters by recipient, orders by sequence, and reads `limit + 1` records in one protected read to set `has_more`. `next_cursor` is the last returned sequence, or the requested cursor if the page is empty. Sequence gaps are normal.

Before committing a page, the client checks epoch, recipient, field types, and immutable content; sequences must be strictly increasing and above the request cursor, and `next_cursor` must equal the last sequence. An empty page cannot claim `has_more`. An invalid page pauses sync with nothing committed.

Never advance the receive cursor from a send acknowledgement or a timestamp. The server never deletes messages after a GET, since the response can be lost. Clients ignore unknown response fields but require mandatory ones; the server rejects unknown request fields. Incompatible changes need a new protocol version.

## 5. Errors

All errors carry `code`, `message`, and `server_epoch` when available. FastAPI validation errors are mapped into the same envelope.

| Failure | Result | Client response |
|---|---|---|
| Invalid username, payload, or type | 422 `INVALID_REQUEST` | Show error; never drop a queued message |
| Same key, different recipient or text | 409 `MESSAGE_ID_CONFLICT` | Mark message failed; no retry |
| Epoch mismatch | 409 `SERVER_EPOCH_CHANGED` | Pause sync; show server restarted |
| Cursor negative or beyond current sequence | 422 `INVALID_CURSOR` | Pause; never silently reset to zero |
| Timeout, disconnect, 5xx, 429 | Retryable | Keep outbox entry; back off (honor `Retry-After`) |
| Unexpected status or malformed/mismatched response | Protocol error | Pause; show diagnostic; never treat as accepted |
| Local transaction fails | Storage error | Keep last committed state; stop and report |
| Request cancelled by lifecycle | Cancellation | Keep pending work; not a rejection |

## 6. Server

A single-process modular monolith in `backend/app/` with four layers. Composition (`main.py`, `config.py`) builds the app, epoch, and wiring. HTTP (`api/routes.py`, `schemas.py`, `errors.py`) decodes requests and maps results to responses, with no mailbox logic. Domain (`domain.py`, `service.py`) holds identity and text rules, use cases, and typed errors, with no FastAPI types. Storage (`repository.py`, `memory_store.py`) does atomic accept-or-replay and inbox reads.

The repository exposes only `accept_or_replay(expected_epoch, message)` and `read_inbox(expected_epoch, recipient, after, limit)`, so duplicate lookup and insert can never be split. The store holds the epoch, a sequence counter, a map from logical key to immutable record, and per-recipient mailbox lists.

Validate payloads before taking the lock. Inside one protected operation, check the epoch, look up the key, then either compare against the existing record or allocate a sequence and insert into both the key map and the mailbox. Serialize JSON after releasing the lock. Inbox reads snapshot under the same lock.

Run one Uvicorn worker with one `asyncio.Lock`, and never wait on I/O inside it. Separate workers have separate memory [2], which would break in-memory mailboxes. Messages and duplicate keys live until exit; deleting keys earlier would let a late retry create a duplicate. A restart loses undelivered messages, which is accepted for this demo. FastAPI is chosen for typed handling and OpenAPI [1].

## 7. Client architecture (both platforms)

**Facade.** Native and headless shells call the same operations: `load()` opens and migrates the store; `identify(name)` saves the username locally; `enqueue(recipient, text)` stores the message and outbox entry atomically and returns the ID after commit; `observeSnapshot()` streams immutable state; `setActive(active)` starts or pauses foreground sync; `requestSync()` wakes the existing loop; `syncOnce()` runs one bounded cycle in manual mode; `setOfflineForTest(offline)` gates the network in tests; `close()` shuts down. Manual and automatic sync share one gate. Snapshots never expose SQL rows, DTOs, or connections.

**Ports.** The core declares `ChatStore` (identity, enqueue, pending list, ack commit, page commit, snapshots), `MessagingTransport` (meta, submit, inbox page), `Clock`, `MessageIdSource`, and `EventSink`; adapters implement them. The core never depends on GRDB, SQLDelight, URLSession, OkHttp, SwiftUI, Compose, or Android `Context`.

**Storage.** Each install or runner has its own SQLite file in app storage (not cache), with foreign keys enabled and versioned migrations that fail loudly. Tables: `identity` (singleton username), `messages` (keyed by sender and client ID; recipient, text, enqueue order, status, acceptance epoch/sequence/time, failure code), `outbox` (pending entries with attempt count and last error, foreign-keyed to messages), and `sync_state` (epoch, cursor, next enqueue order). Index by peer and accepted order; nothing more.

Three transactions carry the reliability guarantees [3]:
1. **Enqueue:** allocate order, insert message and outbox row, commit. Only then clear the composer.
2. **Acceptance:** validate the ack against the stored payload, record acceptance, delete the outbox row, commit. A crash before commit just causes a safe retry.
3. **Receive:** validate the whole page, upsert by key, save cursor and epoch, commit. Any failure rolls back the whole page.

An incoming duplicate with different content is a protocol error, never an overwrite. Self-addressed messages are one row; if an inbox page contains a message still pending locally, the receive transaction also marks it accepted and clears its outbox entry, covering a lost ack. Display accepted messages in sequence order, followed by pending and failed ones in enqueue order.

**Sync engine.** States: Unidentified, Paused, Synchronizing, Waiting, Backoff, Server reset, Protocol error, Storage error. A cycle validates the epoch (setting it only if none is saved), fetches and commits one inbox page, then submits up to 10 pending messages in order. If more work remains, run another cycle promptly; otherwise wait for the poll interval. Transient failures end the cycle and back off. A permanent rejection marks that message failed and removes its outbox row in one transaction. A stuck retryable send blocks later sends to preserve order.

Keep one active sync task plus a generation token so stale completions cannot overwrite newer state; actors and mutexes alone do not prevent overlapping cycles, because Swift actors interleave across `await` [7]. Never hold a transaction across network I/O. OS connectivity callbacks only wake a retry; never require an "internet available" flag, since the local server may be reachable without internet.

The guarantee is eventual retry while the client is active and the server reachable, with duplicate suppression within a server session. There is no promise of immediate delivery, read status, or survival of server restarts. Example: Alice's ack is lost after the server accepted her message; her outbox entry survives, she retries with the same ID, gets the original acceptance back, and commits; Bob receives the message exactly once.

## 8. iOS client

One Swift package with targets `MessagingCore` (domain, facade, sync, ports), `MessagingHTTP` (URLSession, DTOs), `MessagingSQLite` (GRDB store), and `MessagingCLI` (headless runner), plus a SwiftUI app [4][5]. Nothing in the core imports an adapter or the app. Minimum iOS 17 for Observation.

At launch a small `AppContainer` builds config, store, transport, clock, ID source, and one app-scoped client, loads it, then picks the first screen. Use constructor injection, no DI framework. A `@MainActor` observable presentation model [6] maps core snapshots to rows and keeps only transient state (drafts, selection, field errors); it never keeps its own message list. Views never start sync from `.task` or `onAppear`.

On Send, capture the draft, await `enqueue`, and clear it only after commit, keeping any newer edits. On storage failure, keep the draft and show the error.

`MessagingClient` owns the active task, activation, expected epoch, and generation token, and exposes state through `AsyncStream`. The HTTP adapter percent-encodes usernames, sets deadlines and the epoch header, disables caching for inbox GETs, validates responses, and never changes the ID on retry. GRDB (chosen over SwiftData/Core Data for explicit keys and transactions) runs on a serialized queue off the main actor.

Foreground activates the client and triggers a sync; background pauses polling. Background execution is system-controlled [8], so v1 promises nothing while suspended and uses no APNs. The headless runner uses the same targets with its own data directory and runs on macOS; passing it does not prove the iOS app works.

## 9. Android client

Gradle modules: `:messaging-core` (no Android classes; coroutines and Flow), `:messaging-http` (OkHttp, kotlinx.serialization) [14], `:messaging-storage` (SQLDelight, no concrete driver), `:messaging-cli` (JVM runner with `JdbcSqliteDriver`), and `:android-app` (Compose, ViewModels, `AndroidSqliteDriver`) [9][10]. Storage logic never branches by platform. Pin and verify all versions.

An application-scoped `MessagingClient` owns a structured coroutine scope, the sync job, and a Mutex-guarded coordinator [13]. Expose a read-only `StateFlow`, never use `GlobalScope`, never hold the mutex or a transaction across HTTP, and rethrow `CancellationException`. A process-level lifecycle owner activates the client on foreground; Activity recreation reuses it; after process death the client rebuilds from SQLite.

ViewModels expose `StateFlow<ChatUiState>`, collected with `collectAsStateWithLifecycle` [11][12], and use `viewModelScope` only for UI work. Composables never touch the database, HTTP, or ID generation; list keys are message keys. The send flow matches iOS, and both platforms show the same statuses: Queued, Sending, Accepted by server, Failed. No delivered/read marks.

OkHttp runs on both Android and JVM; Retrofit and Ktor add nothing for three endpoints. SQLDelight is chosen for explicit SQL and driver substitution; Room also supports JVM [15] and could replace it behind `ChatStore`. `AppContainer` uses `Context` only to build the driver. WorkManager [16] and FCM are not used in v1. A JVM pass does not prove the Android app works.

## 10. Headless runner contract

Identical on both platforms, using JSON Lines on stdin/stdout with a request ID per command and logs on stderr. Commands: `identify {name}`, `send {recipient, text}` (returns the ID and queued status), `offline {enabled}`, `sync_once` (returns counts of accepted, received, and pending), `snapshot {peer?}`, and `shutdown`.

Use manual sync for deterministic scenarios and automatic sync for reconnect tests. Wait for structured completion or a bounded condition, never a fixed sleep. Compare logical fields only. Tests may inject IDs and clocks, but interoperability tests must use both real HTTP adapters against the real server; a fault wrapper may drop a response after real acceptance.

## 11. Repository layout

`spec/` holds `behavior.md`, `protocol.openapi.yaml`, and `scenarios/`. `.agent/` holds this file and `task.md`. The server lives in `backend/app/`. iOS: `ios/Package.swift`, `ios/Sources/{MessagingCore,MessagingHTTP,MessagingSQLite,MessagingCLI}/`, `ios/App/MessagingIOS/`, `ios/Tests/`. Android: `android/settings.gradle.kts` and one folder per module. Cross-client tests live in `tests/`. Gradle wrapper, Swift package resolution, and Xcode project setup must be reproducible from the repo, with no unrecorded IDE state.

## 12. Local environment

Inject base URL, data directory, run mode, and logging; never hard-code a machine address. Emulators, simulators, and devices reach the host by different hostnames, so composition code resolves it. Allow cleartext HTTP only in development config. The server runs on any local machine; the Swift runner and iOS simulator need macOS with Xcode; the JVM runner runs on macOS or Linux; the Android app needs the Android toolchain. Linux alone cannot validate the iOS app. A cloud-free runtime still downloads packages at build time unless dependencies are vendored.

## 13. Verification

None of these has been run. Required levels: shared fixtures read identically in both languages; core unit tests (queue-first send, stable retry IDs, cancellation, single-flight, ordering); store tests on real SQLite (the three transactions, reopen with queued data, migration failure); server tests (concurrent duplicate POSTs, conflicting payload, routing, paging, epoch reset); cross-language headless runs with roles swapped; failure injection (lost POST response, replayed page, interrupted commit, repeated reconnect hints); and native builds that identify, send, receive, and resume.

Alice/Bob scenario:
1. Alice and Bob exchange messages online.
2. Both go offline; each queues one message.
3. Alice reconnects and sends hers.
4. Alice goes offline again.
5. Bob reconnects, receives Alice's message, and sends his.
6. Alice reconnects and receives Bob's.

At step 5 Alice has not received Bob's message; only step 6 proves it. Measure counts, IDs, payloads, outbox, cursor, epoch, and status. Claim nothing about performance or pass rates without recorded runs.

## 14. Tradeoffs

FastAPI over Flask/Django for typed APIs. One process because shared state stays simple, at the cost of scaling. Short polling over WebSockets for fewer connection states, at the cost of delay and empty requests. SQLite on clients for atomic queue/ack/cursor updates. In-memory server because a restart losing undelivered messages is acceptable here. GRDB and SQLDelight for explicit SQL over SwiftData, Core Data, or Room. A core with thin UI so headless and native share rules. Manual wiring over DI frameworks for a small graph. Foreground-only sync because no background behavior is required. Revisit each if the matching requirement changes.

Future features change the contract first: attachments need payload and transfer rules, reactions need event IDs, groups need membership and authorization. None should move logic into SwiftUI or Compose.

## 15. Open questions

- **Server restart recovery.** After an epoch change, clients enter "Server reset" and stop syncing, but no operation exits that state, so one server restart strands both clients. Decide before writing `spec/behavior.md`: add an explicit reset operation or require clearing client data.
- **Pending messages across a reset.** If a reset exists, decide whether pending messages are resent (possible duplicate) or marked failed.

## 16. References

Framework capabilities only; none is evidence this project works.

1. [FastAPI features](https://fastapi.tiangolo.com/features/)
2. [FastAPI deployment concepts](https://fastapi.tiangolo.com/deployment/concepts/)
3. [SQLite atomic commit](https://www.sqlite.org/atomiccommit.html)
4. [Swift Package Manager](https://docs.swift.org/package-manager/PackageDescription/PackageDescription.html)
5. [GRDB Package.swift](https://github.com/groue/GRDB.swift/blob/master/Package.swift)
6. [SwiftUI model data](https://developer.apple.com/documentation/swiftui/managing-model-data-in-your-app)
7. [Swift concurrency](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/concurrency/)
8. [Apple background strategies](https://developer.apple.com/documentation/backgroundtasks/choosing-background-strategies-for-your-app)
9. [SQLDelight on Android](https://sqldelight.github.io/sqldelight/latest/android_sqlite/)
10. [SQLDelight on JVM](https://sqldelight.github.io/sqldelight/latest/jvm_sqlite/)
11. [Compose UI architecture](https://developer.android.com/develop/ui/compose/architecture)
12. [Compose state](https://developer.android.com/develop/ui/compose/state)
13. [Kotlin shared mutable state](https://kotlinlang.org/docs/shared-mutable-state-and-concurrency.html)
14. [OkHttp](https://square.github.io/okhttp/)
15. [Room multiplatform](https://developer.android.com/kotlin/multiplatform/room)
16. [Android persistent work](https://developer.android.com/develop/background-work/background-tasks/persistent)