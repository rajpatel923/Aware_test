# ios/AGENTS.md

Rules for work under `ios/`. These refine root `AGENTS.md`; read both. Paths are relative to the repository root.

## Scope

The Swift client: one messaging core shared by a SwiftUI app and a headless macOS runner. Tasks A01 (core, adapters, runner) and N01 (native app) in `.agent/task.md`. Nothing below exists yet; do not create files just because they are listed here.

Before writing behavior, read `spec/behavior.md`, `spec/protocol.openapi.yaml`, `spec/scenarios/`, and design sections 3–5, 7, 8, and 10. The spec wins over this file and the design. If the spec is missing or ambiguous, report it and continue only independent work. Never copy or translate Kotlin code; both clients implement the spec independently.

## Commands

| Purpose | Command | Working dir | Status |
|---|---|---|---|
| Build package + CLI | `swift build` | `ios/` | PASS |
| Unit and store tests | `swift test` | `ios/` | PASS |
| Run headless CLI | `.build/debug/messaging-cli --url http://127.0.0.1:8000 --data-dir <dir>` | `ios/` | PASS |
| Build iOS app (simulator) | `xcodebuild -project MessagingApp.xcodeproj -scheme MessagingApp -destination 'platform=iOS Simulator,name=iPhone 17' build` | `ios/` | PASS (BUILD SUCCEEDED) |
| Install on booted simulator | `xcrun simctl install booted <path-to-MessagingApp.app>` | any | PASS |
| Launch on booted simulator | `xcrun simctl launch booted com.example.messaging.ios` | any | PASS |
| Swift acceptance tests | `python -m pytest test_swift_client.py -v` | `tests/` | PASS (7/7) |

## Ownership

iOS tasks own `ios/` only. Never edit `spec/`, `tests/`, `backend/`, `android/`, root instructions, or `.agent/task.md`; propose changes in the handoff. Never fix a client bug by weakening a shared expected result.

## Layout

- `ios/Package.swift`: library targets, the CLI executable, and test targets.
- `ios/Sources/MessagingCore/` with `Domain/`, `Application/`, `Ports/`: domain values, the `MessagingClient` facade, `SyncEngine`, port protocols, immutable snapshots. Standard library and Foundation value types only.
- `ios/Sources/MessagingHTTP/`: URLSession transport, wire DTOs, JSON coding, error mapping.
- `ios/Sources/MessagingSQLite/`: GRDB store, migrations, row mapping, the three transactions, observation.
- `ios/Sources/MessagingCLI/`: headless runner (JSONL commands).
- `ios/App/MessagingIOS/`: `AppContainer`, presentation models, SwiftUI views, lifecycle bridge.
- `ios/Tests/`: unit and adapter tests. Cross-client tests stay in `tests/`.

Dependencies point inward. `MessagingCore` never imports GRDB, URLSession networking, SwiftUI, UIKit, or any adapter. Views and presentation models call only the core; only `AppContainer` and the CLI construct adapters. Do not create empty files or extra packages to match this list.

## Core and concurrency

`MessagingClient` exposes the facade operations in design section 7 and owns the active sync task, activation state, expected epoch, and a generation token. An actor alone does not prevent overlapping cycles, because actor methods interleave across `await`. Keep exactly one active sync task, have `requestSync()` wake it rather than start another, and discard completions whose generation token is stale. `syncOnce()` and automatic sync share one gate.

Never hold a database transaction across a network call. Enqueue must work while a request is in flight. Deactivation cancels sync work and keeps all committed data. State is exposed through `AsyncStream` (or equivalent) with teardown that releases continuations and database observations.

## HTTP adapter

Build URLs from an injected base URL and percent-encode usernames. Use `JSONEncoder`/`JSONDecoder` with DTOs that stay inside this target. Apply the 10 s deadline and `X-Server-Epoch` header, classify statuses per the error table, and handle cancellation. Disable caching for inbox GETs. Validate epoch, IDs, recipient, payload, sequence order, and cursor before returning values to the core. Ignore unknown response fields but require mandatory ones. Never generate a new ID on retry. No decoding on the main actor.

## Storage adapter

GRDB with a serialized `DatabaseQueue`, exposed through async operations so the main actor never blocks. Store the database in Application Support, never Caches or tmp. Enable foreign keys, use versioned migrations, and fail visibly on migration error; never delete the database to recover. Implement the enqueue, acceptance, and receive transactions exactly as in design section 7. A conflicting incoming duplicate is a protocol error, never an overwrite.

Measure text limits in UTF-8 bytes (`text.utf8.count`), never `String.count`. Canonicalize usernames with ASCII-only rules, never locale-aware lowercasing.

## SwiftUI app

Minimum iOS 17 with Observation. At launch, `AppContainer` builds config, store, transport, clock, ID source, and one app-scoped client, loads it, then shows the identify or conversation screen. Use constructor injection, no DI framework or service locator.

The presentation model is `@Observable` and `@MainActor`. It maps core snapshots to rows and holds only transient state (drafts, selection, field errors), never its own message list. Views never start sync from `.task` or `onAppear`; a view may subscribe to state and must cancel on disappear. Losing a subscription never touches the queue or cursor.

On Send: capture the draft and recipient, await `enqueue`, and clear the draft only after commit, keeping any text typed meanwhile. On storage failure, keep the draft and show the error. Statuses: Queued, Sending, Accepted by server, Failed. No delivered or read marks.

Lifecycle: scene activation calls `setActive(true)` and requests a sync; backgrounding pauses polling and keeps queued work. Promise nothing while suspended; no APNs or background tasks in v1. Inject the server base URL; allow cleartext HTTP only in development configuration (App Transport Security exception for the local host).

## Headless runner

Uses the same Core, HTTP, and SQLite targets as the app, with no SwiftUI, hidden windows, or fake messaging logic. Implements the JSONL contract in design section 10: one result per request ID on stdout, logs on stderr. Each instance takes its own data directory and base URL; restarting with the same directory reloads queued messages. A fault-injection transport may wrap the real HTTP adapter. Reference environment is macOS; Linux is unsupported until separately verified.

## Required checks

A01 is done when each has a recorded passing result against real GRDB storage and the real server: the seven client guarantees listed under A01/A02 in `.agent/task.md`. N01 is done when the app builds and runs on the recorded simulator or device and completes identify, send, receive, queue offline, resume and flush, and relaunch with persisted state, with only one sync loop after resume and a responsive UI.

A macOS runner pass proves nothing about the iOS app. Missing Xcode or simulator makes N01 `blocked`, never `done`. Screenshots alone do not prove persistence.

## AGENTS.md files

Any new subdirectory added under `ios/` must include its own `AGENTS.md` that:
- References this file and root `AGENTS.md` as parents.
- Describes the subdirectory's scope, layout, and build/test commands.
- Lists verified commands with working directory and exit status once they pass.

Update this file whenever a task changes the layout, commands, or conventions for `ios/`.

## Done

Pin dependency versions and commit `Package.resolved`. The Xcode project must build from the repository with no unrecorded IDE setup. Review the diff, confirm only `ios/` changed, commit coherent increments, and hand off per root `AGENTS.md`.