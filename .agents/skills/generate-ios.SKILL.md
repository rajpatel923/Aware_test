---
name: generate-ios
description: Generate or regenerate the Spec_drive Swift iOS client from the specification after analysis has produced a task plan with no blocking gaps.
---

# Skill: iOS Implementer

Invoked as `/generate-ios` in Claude Code. Runs the iOS Implementer role defined in `AGENTS.md`.

## What this skill does

Generates the Swift iOS client in `clients/ios/` from the spec. It reads only `spec/` and writes only `clients/ios/`. It never reads `clients/android/` or any previously generated iOS output.

## Prerequisites

Before running this skill:
1. `/analyze` has been run and there are no `[BLOCKER]` gaps.
2. `spec/platform/ios.md` exists.
3. The toolchain is available (macOS with Xcode; see `.agents/TASKS.md` E01).

## Instructions

You are acting as the iOS Implementer. Follow `AGENTS.md` - iOS Implementer role - and `spec/platform/ios.md` exactly.

### Input sources (read these; read nothing else)

- All files in `spec/` (domain, protocol, api, offline-behavior, ui, test, platform/ios)
- The current task plan in `.agents/TASKS.md`

**Do not read `clients/android/`, any previously generated `clients/ios/` output, or git history of generated paths.**

### Output path

All generated files go inside `clients/ios/`. Do not write anywhere else.

### Step 1 - read and plan

Read every relevant spec file. For each rule you will implement, note its ID. Read `spec/platform/ios.md` fully; it contains Swift-specific pitfalls that override naive implementations.

Pay special attention to:
- `I3.1` - username lowercasing: do NOT use `lowercased()`, use ASCII-only byte conversion
- `I3.2` - text length: use `text.utf8.count`, never `text.count` or `text.utf16.count`
- `I3.4` - event IDs: `UUID().uuidString` is uppercase; lowercase once at creation
- `I4.1` - concurrency: actor re-entry at `await` means you need an explicit task gate and generation counter
- `I6.1` - URLSession: ephemeral config, `urlCache = nil`, `waitsForConnectivity = false`

### Step 2 - generate the package structure

Generate `clients/ios/Package.swift` with these targets (see `spec/platform/ios.md` section 2):

| Target | Kind                                           |
|---|------------------------------------------------|
| `MessagingCore` | library - domain, protocol, sync engine, ports |
| `MessagingHTTP` | library - URLSession transport, wire DTOs      |
| `MessagingStore` | library - GRDB storage, migrations             |
| `messaging-runner` | executable - headless runner                   |
| Test targets | one per library                                |

`MessagingCore` MUST NOT import GRDB, URLSession networking, SwiftUI, or UIKit (`I2.1`).

### Step 3 - implement each layer in order

#### Domain layer (`MessagingCore`)
Implement all `D…` rules. Each piece of logic MUST have a short comment citing its rule ID, e.g. `// D1.1`.

Key implementations:
- Username canonicalization (D1.1): strip ASCII whitespace → ASCII-only lowercase → validate `[a-z0-9_]{1,32}`
- Text validation (D4.1): UTF-8 byte count 1–4096, exact storage (D4.2)
- Event creation: generate lowercase UUID (D3, I3.4), assign `local_order` atomically (D5.1)
- Status transitions: `queued → accepted`, `queued → failed` only (D6.2)

#### Storage adapter (`MessagingStore`)
Implement schema and the three critical transactions (O2.3, O4.1, P7.4):
1. Enqueue: allocate `local_order`, insert event + outbox entry, advance counter - one `write` block (I5.3)
2. Acceptance: update status/seq/epoch, delete outbox entry - one `write` block
3. Receive page: upsert events, save cursor - one `write` block; roll back everything on any failure

Use `DatabaseMigrator` with named, append-only migrations (I5.2). Enable foreign keys (I5.2). Database file in `--data-dir` for the runner.

#### HTTP adapter (`MessagingHTTP`)
Implement all `A…` and `P…` transport rules:
- Ephemeral `URLSession` (I6.1)
- `X-Server-Epoch` header on every POST and inbox GET (A3.1)
- Validate response: check epoch, identifiers, recipient, seq monotonicity within pages (P5.5, P7.3)
- Do not retry internally; surface outcomes to the sync engine (A5.2)

#### Sync engine (`MessagingCore`)
Implement all `O…` rules:
- One cycle: session check → pull → submit up to 10 (O5.2, O5.3)
- Pull before submit (O5.3)
- At most one cycle at a time; generation counter for cancellation (O6.1, O6.3, I4.1)
- Backoff: 1, 2, 4, 8, 16, 30 s (O8.1)
- Sync states: idle, syncing, offline, paused, server_reset, incompatible, protocol_error, storage_error (O7)

#### Headless runner (`messaging-runner`)
Implement all commands from `spec/test.md` section 2:
`identify`, `send`, `network`, `sync_once`, `snapshot`, `fault`, `reset_session`, `shutdown`

Start in manual mode (T2.5). Flags: `--base-url`, `--data-dir`, `--auto`. JSON Lines on stdin/stdout, logs to stderr only (I8.1, I8.2).

`network` and `fault` live in a transport wrapper in the runner, not in `MessagingCore` (I8.3, T2.3, T2.4).

#### iOS app (`MessagingApp` via XcodeGen)
Implement `U…` rules:
- Identify screen (U1): name field, submit, inline validation error, no network wait
- Conversation screen (U2–U6): peer selector, message list in display order, composer, sync banner
- `@Observable @MainActor` view model per screen (I7.1)
- `scenePhase` drives activity (I7.2)
- `NSAllowsLocalNetworking = true` in Info.plist (I7.4)

### Step 4 - build and test

```bash
cd clients/ios
swift build
swift test
```

Fix any build or test failure inside `clients/ios/` only. If a failure reveals a spec gap, stop and report it; do not invent behavior.

### Step 5 - handoff

End with:
- Role: iOS Implementer
- Files generated: list every new file
- Rules implemented: all rule IDs cited in the code, grouped by file
- Build result: PASS or FAIL (exact command and exit status)
- Test result: PASS / FAIL / NOT RUN (exact command and exit status)
- Assumptions: any detail the spec leaves open and what choice you made
- Spec gaps: any rule that was ambiguous or missing (route to Analyzer)
