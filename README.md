# Spec-Driven Messaging Generator

A code generator that turns a written specification into two independent messaging clients: Swift (iOS) and Kotlin (Android), that behave identically against one shared server. The generator is the deliverable; the messaging app is the evaluation example.

**Core promise:** delete `clients/ios/` and `clients/android/`, follow the steps below, and get back working clients whose behavior matches the spec.

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

When the spec and implementation disagree, the spec wins. When two spec files disagree, stop and report, never choose one silently.

---

## The agentic coding generator

The generator works through four roles defined in `AGENTS.md`. Each role is a Claude Code slash command backed by a prompt file in `.agents/skills/`:

| Role | Command | Skill file | What it does |
|---|---|---|---|
| Specification Analyzer | `/analyze` | `.agents/skills/analyze.SKILL.md` | Reads spec, identifies affected rules, flags gaps, writes plan to `.agents/TASKS.md`. Writes no code. |
| iOS Implementer | `/generate-ios` | `.agents/skills/generate-ios.SKILL.md` | Generates Swift client in `clients/ios/` from spec only. Never reads `clients/android/`. |
| Android Implementer | `/generate-android` | `.agents/skills/generate-android.SKILL.md` | Generates Kotlin client in `clients/android/` from spec only. Never reads `clients/ios/`. |
| Verifier | `/verify` | `.agents/skills/verify.SKILL.md` | Builds both clients, runs all scenarios in both role assignments, records PASS/FAIL/NOT RUN. Cannot edit code or spec. |

Roles run in order: Analyzer → Implementers (either order or parallel) → Verifier.

**Tool:** Claude Code CLI (`claude`). The evaluator runs the slash commands in a Claude Code session open at the repository root.

When you type `/generate-ios`, Claude Code loads `.agents/skills/generate-ios.SKILL.md` as the agent's instructions. The agent reads only `spec/`, writes only `clients/ios/`, and cites the rule ID on every piece of behavior logic. `.agents/skills/` files are the authoritative prompt templates; `.claude/commands/` files are one-liners that load the skill and invoke the role. Improving a skill never requires touching the command file.

---

## Regenerating the clients

**Prerequisites:**
- macOS with Xcode (for iOS)
- JDK 17, Android SDK, Gradle (for Android)
- Python 3.11+ with pip (for the server and harness)
- Claude Code CLI

**Step 1: delete generated code:**
```bash
rm -rf clients/ios clients/android
```

**Step 2: open Claude Code at the repo root and run the roles in order:**

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

Each command records its handoff in `.agents/TASKS.md`. The full workflow procedure is in `.agents/WORKFLOW.md`.

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

Results are recorded in `.agents/TASKS.md` under task X01. A headless pass does not prove the native app works; both are required (`spec/test.md` T1.3).