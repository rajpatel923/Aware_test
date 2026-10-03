# Local Messaging App

A fully local messaging system: one Python/FastAPI server and two independent clients: Swift (macOS headless + iOS app skeleton) and Kotlin (JVM headless + Android Compose app). Both clients speak the same HTTP/JSON protocol and are tested against the same server.

---

## Prerequisites

| Tool | Verified version |
|---|---|
| Python | 3.12.9 (miniforge3) |
| Swift | 6.4 (swiftlang-6.4.0.34.1, CommandLineTools) |
| JDK | 22 (2024-03-19) |
| Android SDK | `~/Library/Android/sdk` (API 35, build-tools 36.0.0) |
| Kotlin | 2.0.21 (via Gradle) |
| Gradle | 8.6 (wrapper at `android/gradlew`) |
| Xcode | 27 (iOS 18 SDK) — N01 verified on iPhone 17 simulator |

---

## Server

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The server runs at `http://127.0.0.1:8000`. It stores mailboxes in memory; a restart clears all messages and issues a new epoch. Clients detect this and reset their cursors.

---

## Swift headless client

Build (from repo root):

```bash
cd ios && swift build
```

Binary: `ios/.build/debug/messaging-cli`

Run:

```bash
ios/.build/debug/messaging-cli --url http://127.0.0.1:8000 --data-dir /tmp/alice-data
```

The client reads JSON Lines from stdin and writes JSON Lines to stdout. Each line is `{"id":"<n>","cmd":"<cmd>","args":{...}}`. Supported commands: `identify`, `send`, `offline`, `fault`, `sync_once`, `snapshot`, `reset_session`, `shutdown`.

---

## Kotlin headless client

Build (from `android/`):

```bash
cd android && ./gradlew :messaging-cli:jar --no-daemon
```

JAR: `android/messaging-cli/build/libs/messaging-cli.jar`

Run:

```bash
java -jar android/messaging-cli/build/libs/messaging-cli.jar \
  --url http://127.0.0.1:8000 --data-dir /tmp/bob-data
```

Same JSON Lines protocol as the Swift client.

---

## Android Compose app

Build (from `android/`):

```bash
cd android && ANDROID_HOME=~/Library/Android/sdk ./gradlew :android-app:assembleDebug --no-daemon
```

APK: `android/android-app/build/outputs/apk/debug/android-app-debug.apk`

Install and launch on a running emulator or device:

```bash
adb install android-app/build/outputs/apk/debug/android-app-debug.apk
adb shell am start -n com.example.messaging.app/.MainActivity
```

The app connects to `http://10.0.2.2:8000` (Android emulator loopback to host). Start the server on the host before launching the app. On first launch, enter your name. The sync loop runs every 3 seconds.

---

## Tests

### Server unit tests (B01)

```bash
cd backend && .venv/bin/pytest tests/ -v
# 27 passed
```

### Cross-client harness self-tests (V01)

```bash
cd tests && python -m pytest test_harness.py -v
# 9 passed
```

### Swift headless acceptance (A01)

```bash
cd ios && swift build          # build first
cd tests && python -m pytest test_swift_client.py -v
# 7 passed
```

### Kotlin headless acceptance (A02)

```bash
cd android && ./gradlew :messaging-cli:jar --no-daemon   # build first
cd tests && python -m pytest test_kotlin_client.py -v
# 7 passed
```

### Cross-language interoperability (X01)

```bash
python -m pytest tests/test_cross_language.py -v
# 2 passed  (alice=Swift/bob=Kotlin and alice=Kotlin/bob=Swift)
```

### Native app (N02)

Verified manually on Medium_Phone_API_35 emulator (API 35, arm64-v8a). See task evidence E-N02 in `.agent/task.md`.

### Native iOS app (N01)

```bash
cd ios
xcodebuild -project MessagingApp.xcodeproj \
  -scheme MessagingApp \
  -destination 'platform=iOS Simulator,name=iPhone 17' \
  build
xcrun simctl install booted MessagingApp.xcodeproj/../DerivedData/*/Build/Products/Debug-iphonesimulator/MessagingApp.app
xcrun simctl launch booted com.example.messaging.ios
```

Verified on iPhone 17 simulator (Xcode 27, iOS 18): identify screen → conversation screen with persisted messages, all accepted, pending: 0.

---

## Architecture

```
spec/             HTTP contract + behavior rules + test scenarios
backend/          FastAPI server (Python 3.12, in-memory mailboxes)
ios/              Swift package: MessagingCore | MessagingHTTP | MessagingSQLite | MessagingCLI
android/          Gradle project: :messaging-core | :messaging-http | :messaging-storage | :messaging-cli | :android-app
tests/            Cross-client harness (Python) + acceptance tests
```

Each client's core holds all messaging behavior. Network and storage are injected; the UI (Compose) and headless runner are thin wrappers over the same core and real adapters.

---

## Limitations

- Server keeps mailboxes in memory; all messages are lost on restart. Clients detect the epoch change and reset cursors automatically.
- No authentication. The server trusts the `sender` field in every POST.
- Cleartext HTTP only (`usesCleartextTraffic="true"` + network security config for 10.0.2.2).
- SwiftUI iOS app (N01) requires Xcode and an iOS Simulator; verified with Xcode 27 / iPhone 17 simulator.
- No background sync on Android; foreground-only (ViewModel scope).

---

## Files authored by agent

All files in `backend/`, `ios/`, `android/`, `tests/`, `spec/scenarios/` (JSON fixtures), `.agent/`, and this README were created or substantially modified by the coding agent in this session.
