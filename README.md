# Spec-Driven Messaging Generator

A code generator that turns a written specification into two independent messaging clients: Swift (iOS) and Kotlin (Android), that behave identically against one shared server. The generator is the deliverable; the messaging app is the evaluation example.

**Core promise:** delete `clients/ios/` and `clients/android/`, follow the steps below, and get back working clients whose behavior matches the spec.

Generated code is disposable. A fix to generated behavior is always a spec change followed by regeneration, never a hand edit inside `clients/`.

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