# Platform: iOS (Swift)

Status: draft. Rules carry IDs (`I…`).

This file defines how the shared spec is realized on iOS: language, libraries, structure, platform-specific pitfalls, and commands. It adds no behavior. Every behavioral rule comes from `domain.md`, `protocol.md`, `api.md`, `offline-behavior.md`, `ui.md`, and `test.md`. If this file seems to require behavior those files do not define, that is a spec bug: report it.

## 1. Toolchain

- Language: Swift with Swift Concurrency (`async`/`await`, actors).
- App minimum: iOS 17 (for the Observation framework).
- Headless runner: macOS command-line executable. Linux is not supported.
- Requires macOS with Xcode. Exact Xcode and Swift versions are recorded in `.agent/TASKS.md` (E01).
- Project generation: XcodeGen, from a `project.yml` in the generated output. A hand-maintained `.xcodeproj` cannot be regenerated reliably by an agent; `project.yml` is plain text and can.

I1.1 Libraries are limited to Apple frameworks plus **GRDB** (SQLite). No other third-party dependency without a spec change.

I1.2 Use the latest stable GRDB release that builds with the recorded Xcode. Pin it exactly in `Package.swift`, commit `Package.resolved`, and report the version in the handoff.

## 2. Structure

Generated output lives at `clients/ios/`. It contains one Swift package plus the app:

| Target | Kind | Contains | May depend on |
|---|---|---|---|
| `MessagingCore` | library | Domain, protocol, sync engine, ports (`Storage`, `Transport`, `Clock`, `IDSource`) | Swift standard library, Foundation value types |
| `MessagingHTTP` | library | `URLSession` transport, wire DTOs, error mapping | `MessagingCore`, Foundation |
| `MessagingStore` | library | GRDB storage, migrations, transactions | `MessagingCore`, GRDB |
| `messaging-runner` | executable | Headless runner (`test.md` section 2) | all three libraries |
| `MessagingApp` | iOS app (via XcodeGen) | SwiftUI screens, view models, app composition | all three libraries |
| Test targets | tests | Unit tests per library, fixtures from `test.md` section 6 | the library under test |

I2.1 `MessagingCore` MUST NOT import GRDB, `URLSession` networking, SwiftUI, or UIKit. Only the app and the runner construct adapters.

I2.2 The app and the runner MUST use the same three libraries. No messaging logic exists in either entry point.

## 3. Domain pitfalls

These are the places a straightforward Swift implementation breaks the shared rules.

I3.1 **Username lowercasing** (`domain.md` D1.1). Do not use `lowercased()`: it is Unicode-aware, so the Kelvin sign `K` (U+212A) becomes ASCII `k`, turning an invalid name into a valid one. Convert only the bytes `A`–`Z`, then validate.

I3.2 **Text length** (D4.1). Use `text.utf8.count`, never `text.count` (grapheme clusters) or `text.utf16.count`.

I3.3 **No normalization** (D4.2). Never apply `precomposedStringWithCanonicalMapping` or similar; store and send text exactly as received.

I3.4 **Event IDs** (D3). `UUID().uuidString` is uppercase. Lowercase it once at creation and store the lowercase form.

I3.5 **Timestamps** (`api.md` section 2). Parse and format `accepted_at` with `ISO8601DateFormatter` including `.withFractionalSeconds`; display only.

## 4. Concurrency

I4.1 A single `MessagingClient` actor owns sync. Actor isolation alone does not prevent overlapping cycles, because actors re-enter at every `await`. Keep one sync `Task` and a generation counter; ignore results from a superseded generation (`offline-behavior.md` O6.1, O6.3).

I4.2 Never hold a GRDB transaction across an `await` on the network (O6.2).

I4.3 Treat `CancellationError` and `URLError.cancelled` as cancellation, not network failure (O4.3).

I4.4 State reaches the UI through an `AsyncStream` (or Observation) of immutable snapshots. Views never call storage or HTTP directly.

## 5. Storage

I5.1 GRDB `DatabaseQueue`. Database file in Application Support for the app; in the `--data-dir` directory for the runner.

I5.2 Enable foreign keys. Use GRDB's `DatabaseMigrator` with named, append-only migrations. A failed migration enters `storage_error` (O11.3); never delete the database.

I5.3 The transactions in `offline-behavior.md` O11.2 each run in one `write` block.

## 6. HTTP

I6.1 Use a dedicated `URLSession` with an ephemeral configuration: `urlCache = nil`, `requestCachePolicy = .reloadIgnoringLocalCacheData`, `timeoutIntervalForRequest = 10`, and `waitsForConnectivity = false`. Waiting for connectivity would hide offline outcomes from the outbox (`api.md` A5.2).

I6.2 Encode with `JSONEncoder`, keys exactly as in `api.md` (no automatic key conversion that could alter names). Decode with `JSONDecoder` and then validate per `protocol.md` P5.5 and P7.3; decoding success alone is not validation.

I6.3 Percent-encode the username in the mailbox path.

## 7. App

I7.1 SwiftUI with an `@Observable`, `@MainActor` view model per screen, holding only transient UI state (drafts, selection, errors).

I7.2 `scenePhase` drives activity: `.active` → active; `.background` → inactive (O10.1–O10.3). No background tasks or push notifications (O10.5).

I7.3 Server base URL comes from configuration, defaulting to `http://127.0.0.1:8000`. The simulator reaches the host Mac at `127.0.0.1`. A physical device needs the Mac's LAN address.

I7.4 Plain HTTP is allowed only for local networking: set `NSAppTransportSecurity` → `NSAllowsLocalNetworking = true`. Do not use `NSAllowsArbitraryLoads`. On a physical device, also provide `NSLocalNetworkUsageDescription`.

## 8. Headless runner

I8.1 Start-up: `messaging-runner --base-url <url> --data-dir <path>`. Manual mode is the default (`test.md` T2.5); `--auto` enables timers.

I8.2 Reads JSON Lines on stdin, writes one result line per request to stdout, flushing after each line. Logs go to stderr only.

I8.3 The `network` and `fault` commands are implemented by a transport wrapper in the runner around the real `MessagingHTTP` transport, never inside `MessagingCore` (T2.3, T2.4).

## 9. Commands

All commands are **unverified** until run and recorded in `.agent/TASKS.md`. Working directory: the iOS generated path.

| Purpose | Command |
|---|---|
| Build libraries and runner | `swift build` |
| Unit tests | `swift test` |
| Build runner for the harness | `swift build -c release --product messaging-runner` |
| Generate Xcode project | `xcodegen generate` |
| Build app for simulator | `xcodebuild -project MessagingApp.xcodeproj -scheme MessagingApp -destination 'platform=iOS Simulator,name=<device>' build` |

The simulator name comes from the E01 inventory. Once a command is verified, record the exact form here.