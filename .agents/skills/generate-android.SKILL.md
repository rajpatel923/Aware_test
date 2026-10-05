---
name: generate-android
description: Generate or regenerate the Spec_drive Kotlin Android client from the specification after analysis has produced a task plan with no blocking gaps.
---

# Skill: Android Implementer

Invoked as `/generate-android` in Claude Code. Runs the Android Implementer role defined in `AGENTS.md`.

## What this skill does

Generates the Kotlin Android client in `clients/android/` from the spec. It reads only `spec/` and writes only `clients/android/`. It never reads `clients/ios/` or any previously generated Android output.

## Prerequisites

Before running this skill:
1. `/analyze` has been run and there are no `[BLOCKER]` gaps.
2. `spec/platform/android.md` exists.
3. The toolchain is available (JDK 17, Android SDK, Gradle wrapper; see `.agents/TASKS.md` E01).

## Instructions

You are acting as the Android Implementer. Follow `AGENTS.md` - Android Implementer role - and `spec/platform/android.md` exactly.

### Input sources (read these; read nothing else)

- All files in `spec/` (domain, protocol, api, offline-behavior, ui, test, platform/android)
- The current task plan in `.agents/TASKS.md`

**Do not read `clients/ios/`, any previously generated `clients/android/` output, or git history of generated paths.**

### Output path

All generated files go inside `clients/android/`. Do not write anywhere else.

### Step 1 - read and plan

Read every relevant spec file. For each rule you will implement, note its ID. Read `spec/platform/android.md` fully; it contains Kotlin-specific pitfalls that override naive implementations.

Pay special attention to:
- `K3.1` - username lowercasing: do NOT use `lowercase()`, convert only `'A'..'Z'` manually
- `K3.2` - text length: use `text.encodeToByteArray(throwOnInvalidSequence = true).size`; the default silently replaces lone surrogates
- `K4.1` - concurrency: guard the sync job with a `Mutex` and generation counter; never use `GlobalScope`
- `K4.3` - always rethrow `CancellationException`; never classify it as a network failure
- `K6.1` - OkHttp: `retryOnConnectionFailure(false)`, `callTimeout(10, SECONDS)`, no cache

### Step 2 - generate the module structure

Generate `clients/android/` with these Gradle modules (see `spec/platform/android.md` section 2):

| Module | Kind                                                                         |
|---|------------------------------------------------------------------------------|
| `:core` | Kotlin/JVM library - domain, protocol, sync engine, ports                    |
| `:http` | Kotlin/JVM library - OkHttp transport, wire DTOs                             |
| `:store` | Kotlin/JVM library - SQLDelight schema, queries, transactions                |
| `:runner` | JVM application - headless runner; supplies `JdbcSqliteDriver`               |
| `:app` | Android application - Compose UI, ViewModels; supplies `AndroidSqliteDriver` |

`:core` MUST NOT depend on Android classes, OkHttp, SQLDelight, or Compose (`K2.1`).

Pin all versions in `gradle/libs.versions.toml` (`K1.2`). Include the Gradle wrapper (`K1.3`).

### Step 3 - implement each layer in order

#### Domain layer (`:core`)
Implement all `D…` rules. Each piece of logic MUST have a short comment citing its rule ID, e.g. `// D1.1`.

Key implementations:
- Username canonicalization (D1.1): strip ASCII whitespace → convert `A-Z` to `a-z` byte-by-byte → validate `[a-z0-9_]{1,32}`
- Text validation (D4.1): `encodeToByteArray(throwOnInvalidSequence = true).size`, 1–4096 bytes
- Text storage (D4.2): no normalization, exact bytes preserved
- Event IDs (K3.4): `UUID.randomUUID().toString()` - already lowercase
- Status transitions (D6.2): `queued → accepted`, `queued → failed` only

#### Storage adapter (`:store`)
Implement SQLDelight schema and the three critical transactions (O2.3, O4.1, P7.4):

Tables (from `domain.md` sections 7, 8):
- `identity`: singleton row, canonical username
- `events`: `(sender, event_id)` primary key; all local event fields
- `outbox`: `(sender, event_id)` primary key, foreign key to events; pending rows only
- `sync_state`: singleton row, epoch + cursor

Transactions in one `transaction { }` block each (K5.3):
1. Enqueue: allocate `local_order`, insert event + outbox entry, commit
2. Acceptance: update event status/seq/epoch, delete outbox entry, commit
3. Receive page: upsert events, save cursor, commit; roll back entire page on any failure

Enable foreign keys on both drivers explicitly (K5.2). Append-only migrations in `.sqm` files. Failed migration → `storage_error`, never delete the database.

#### HTTP adapter (`:http`)
Implement all `A…` and `P…` transport rules:
- One shared `OkHttpClient` with `retryOnConnectionFailure(false)` (K6.1)
- `X-Server-Epoch` header on every POST and mailbox GET (A3.1)
- kotlinx.serialization with `ignoreUnknownKeys = true` for responses (K6.2, A1.6)
- Validate response after decoding: epoch, identifiers, recipient, seq monotonicity (P5.5, P7.3)
- URL-encode username with `HttpUrl.Builder.addPathSegment` (K6.3)

#### Sync engine (`:core`)
Implement all `O…` rules with Kotlin coroutines:
- One cycle: session check → pull → submit up to 10 (O5.2, O5.3)
- Pull before submit (O5.3)
- One sync job at a time; Mutex + generation counter for cancellation (O6.1, O6.3, K4.1)
- Backoff: 1, 2, 4, 8, 16, 30 s (O8.1)
- Sync states exposed as a read-only `StateFlow` (K4.4)

#### Headless runner (`:runner`)
Implement all commands from `spec/test.md` section 2:
`identify`, `send`, `network`, `sync_once`, `snapshot`, `fault`, `reset_session`, `shutdown`

Start in manual mode (T2.5). Flags: `--base-url`, `--data-dir`, `--auto`. JSON Lines on stdin/stdout, logs to stderr only (K8.1, K8.2).

`network` and `fault` live in a transport wrapper in `:runner`, not in `:core` (K8.3, T2.3, T2.4).

Use `JdbcSqliteDriver` in `:runner`. The harness runs the installed distribution, not `gradlew run` (K8.4).

#### Android app (`:app`)
Implement `U…` rules:
- Identify screen (U1): name field, submit, inline validation, no network wait
- Conversation screen (U2–U6): peer selector, message list in display order, composer, sync banner
- One `ViewModel` per screen; view models receive the client from the application (K7.1)
- `ProcessLifecycleOwner` drives activity (K7.2)
- Debug base URL: `http://10.0.2.2:8000` (K7.3)
- `INTERNET` permission; cleartext HTTP only in debug via network security config for `10.0.2.2` and `localhost` (K7.4)
- Use `AndroidSqliteDriver` for database (K5.1)

Collect state with `collectAsStateWithLifecycle`. Composables never call storage or HTTP (K4.4).

### Step 4 - build and test

```bash
cd clients/android
./gradlew :core:test :http:test :store:test
./gradlew :runner:installDist
```

Fix any failure inside `clients/android/` only. If a failure reveals a spec gap, stop and report it; do not invent behavior.

### Step 5 - handoff

End with:
- Role: Android Implementer
- Files generated: list every new file
- Rules implemented: all rule IDs cited in the code, grouped by module
- Build result: PASS or FAIL (exact command and exit status)
- Test result: PASS / FAIL / NOT RUN (exact command and exit status)
- Library versions pinned: list every pinned version from `libs.versions.toml`
- Assumptions: any detail the spec leaves open and what choice you made
- Spec gaps: any rule that was ambiguous or missing (route to Analyzer)
