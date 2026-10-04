# Spec-Driven Messaging Generator

A code generator that turns a written specification into two independent messaging clients — Swift (iOS) and Kotlin (Android) — that behave identically against one shared server. The generator is the deliverable; the messaging app is the evaluation example.

**Core promise:** delete `clients/ios/` and `clients/android/`, follow the steps below, and get back working clients whose behavior matches the spec.

## Repository layout

| Path               | What it is                                           | Authored by |
|--------------------|------------------------------------------------------|---|
| `spec/`            | Source of truth for all behavior                     | Hand-written |
| `skills/`          | Role-specific prompt files used by the generator     | Hand-written |
| `server/`          | Small FastAPI server (not under generator discipline) | Hand-written |
| `AGENTS.md`        | Agent roles, permissions, and handoff rules          | Hand-written |
| `CLAUDE.md`        | Per-session agent instructions                       | Hand-written |
| `DESIGN.md`        | Full design rationale                                | Hand-written |
| `.agent/TASKS.md`  | Work queue and verification evidence                 | Hand-written + agent-updated |
| `server/`          | FastAPI server    | Hand-written |
| `clients/ios/`     | **Generated** Swift client                           | Generated |
| `clients/android/` | **Generated** Kotlin client                          | Generated |

Generated code is disposable. A fix to generated behavior is always a spec change followed by regeneration, never a hand edit inside `clients/`.

---

## The spec

Every behavioral rule is in `spec/`. Each file owns one concern:

| File | What it defines |
|---|---|
| `product.md` | User-facing requirements and scope |
| `domain.md` | Entities, username rules, text rules, statuses (`D…` rules) |
| `protocol.md` | Event envelope, idempotency, sequencing, cursors (`P…` rules) |
| `api.md` | HTTP endpoints, wire format, error codes (`A…` rules) |
| `offline-behavior.md` | Outbox, sync cycle, retries, lifecycle (`O…` rules) |
| `ui.md` | Screens and display (`U…` rules) |
| `test.md` | Headless runner contract, Gherkin scenarios, fixtures (`T…` rules) |
| `platform/ios.md` | Swift-specific choices, pitfalls, build commands (`I…` rules) |
| `platform/android.md` | Kotlin-specific choices, pitfalls, build commands (`K…` rules) |

When the spec and implementation disagree, the spec wins. When two spec files disagree, stop and report — never choose one silently.

---

## The agentic harness

The generator works through four roles defined in `AGENTS.md`. Each role is a Claude Code slash command backed by a prompt file in `skills/`:

| Role | Command | Skill file | What it does |
|---|---|---|---|
| Specification Analyzer | `/analyze` | `skills/analyze.md` | Reads spec, identifies affected rules, flags gaps, writes plan to `.agent/TASKS.md`. Writes no code. |
| iOS Implementer | `/generate-ios` | `skills/generate-ios.md` | Generates Swift client in `clients/ios/` from spec only. Never reads `clients/android/`. |
| Android Implementer | `/generate-android` | `skills/generate-android.md` | Generates Kotlin client in `clients/android/` from spec only. Never reads `clients/ios/`. |
| Verifier | `/verify` | `skills/verify.md` | Builds both clients, runs all scenarios in both role assignments, records PASS/FAIL/NOT RUN. Cannot edit code or spec. |

Roles run in order: Analyzer → Implementers (either order or parallel) → Verifier.

**Tool:** Claude Code CLI (`claude`). The evaluator runs the slash commands in a Claude Code session open at the repository root.

---

## Regenerating the clients

**Prerequisites:**
- macOS with Xcode (for iOS)
- JDK 17, Android SDK, Gradle (for Android)
- Python 3.11+ with pip (for the server and harness)
- Claude Code CLI

**Step 1 — delete generated code:**
```bash
rm -rf clients/ios clients/android
```

**Step 2 — open Claude Code at the repo root and run the roles in order:**

```
/analyze
```
Review the output. If the analyzer reports `[BLOCKER]` gaps, resolve them in the spec before continuing.

```
/generate-ios
/generate-android
```
These can be run in parallel in two Claude Code sessions, or sequentially. Each session should have the repo root as its working directory.

```
/verify
```

Each command records its handoff in `.agent/TASKS.md`. The full workflow procedure is in `.agent/WORKFLOW.md`.

---

## The server

The server is hand-written and does not participate in regeneration. It implements `spec/api.md` and `spec/protocol.md`.

```bash
cd server
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Runs at `http://127.0.0.1:8000`.

- iOS Simulator reaches it at `127.0.0.1:8000` (default).
- Android Emulator reaches it at `10.0.2.2:8000`.
- Physical devices need the Mac's LAN address.

**Server tests:**
```bash
cd server
pytest
```

---

## Building the clients

**iOS:**
```bash
cd clients/ios
swift build                          # all targets
swift test                           # unit tests
swift build -c release --product messaging-runner   # headless runner
xcodegen generate                    # generate Xcode project
```

**Android:**
```bash
cd clients/android
./gradlew :core:test :http:test :store:test    # unit tests
./gradlew :runner:installDist                  # headless runner
./gradlew :app:assembleDebug                   # Android app
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

---

## Running verification scenarios

The cross-client test harness (`harness/`) runs the Gherkin scenarios from `spec/test.md` with one real runner of each language against the real server. Each scenario runs twice: Swift as Alice first, then Kotlin as Alice.

```bash
# Start the server first (see above)
cd harness
pip install -r requirements.txt
pytest test_cross_language.py -v
```

Results are recorded in `.agent/TASKS.md` under task X01. A headless pass does not prove the native app works; both are required (`spec/test.md` T1.3).

---

## Attribution

| Artifact | Authored by |
|---|---|
| `spec/`, `DESIGN.md`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `skills/` | Hand-written by the author; AI (Claude) used for drafts, with human review and editing |
| `server/` | Hand-written |
| `harness/` | Hand-written |
| `clients/ios/` | Generated by Claude Code running the iOS Implementer role (`/generate-ios`) |
| `clients/android/` | Generated by Claude Code running the Android Implementer role (`/generate-android`) |
| `.agent/TASKS.md` evidence sections | Updated by Claude Code running the Verifier role (`/verify`) |

Generated commits carry the prefix `gen(ios):` or `gen(android):` and state the model and spec revision used. Hand-written commits carry `spec:`, `server:`, `harness:`, `generator:`, or `docs:` prefixes.

---

## Design rationale

See `DESIGN.md` for the full rationale: why the protocol uses typed events and client-generated IDs, why each spec file owns exactly one concern, why pull happens before submit, and how the harness keeps the oracle honest.

Key design choices:
- **Typed event envelope** (`protocol.md` P3): extensible without changing the sync engine
- **Client-generated IDs + idempotent server** (`protocol.md` P6): safe retry even when responses are lost
- **Cursor-based pull** (`protocol.md` P7): server never deletes on read; a lost response is just pulled again
- **Pull before submit** (`offline-behavior.md` O5.3): both clients produce the same trace in the assignment's step 7
- **Strict requests, tolerant responses** (`api.md` A1.6): server can grow without breaking older generated clients
