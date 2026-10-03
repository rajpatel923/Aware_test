# Environment inventory (E01)

Recorded on macOS (Darwin arm64). Commands run from the repository root unless noted.

## Python

| Item | Result | Command | Exit |
|---|---|---|---|
| Python | 3.12.9 (miniforge3) | `python3 --version` | 0 |
| pip | 25.0.1 | `pip3 --version` | 0 |
| venv / requirements | not created yet | — | — |

Interpreter: `/Users/rajpatel/miniforge3/bin/python3` (via miniforge3).  
No `requirements.txt` yet; B01 creates it.

## Xcode and Swift

| Item | Result | Command | Exit |
|---|---|---|---|
| Swift | 6.4 (swiftlang-6.4.0.34.1) | `swift --version` | 0 |
| Xcode app | **not installed** — only CLT at `/Library/Developer/CommandLineTools` | `xcodebuild -version` | 1 |
| iOS Simulator (`simctl`) | **not available** — requires Xcode app | `xcrun simctl list devices` | 1 |

Swift 6.4 supports strict concurrency and the `Observation` framework used by the SwiftUI app.  
The headless runner (`swift build`, `swift run`) works without Xcode. The iOS native app (`xcodebuild`) does **not**: N01 is `blocked` until Xcode is installed.

## JDK

| Item | Result | Command | Exit |
|---|---|---|---|
| JDK | OpenJDK 22 (2024-03-19, build 22+36-2370) | `java --version` | 0 |
| `kotlinc` | not in PATH | `kotlinc -version` | 127 |
| Gradle (system) | not in PATH | `gradle --version` | 127 |

Kotlin and Gradle are used through the Gradle wrapper (`./gradlew`); standalone installs are not required.

## Android SDK

| Item | Result | Command | Exit |
|---|---|---|---|
| SDK root | `~/Library/Android/sdk` | `ls ~/Library/Android/sdk` | 0 |
| `ANDROID_HOME` | **not set** in environment | — | — |
| ADB | 1.0.41 (37.0.1-15733141) | `adb --version` (via full path) | 0 |
| Platforms | android-37.0 | `ls ~/Library/Android/sdk/platforms/` | 0 |
| Build-tools | 36.0.0 | `ls ~/Library/Android/sdk/build-tools/` | 0 |
| System images | android-35, android-37.2 | `ls ~/Library/Android/sdk/system-images/` | 0 |
| AVDs | Medium_Phone_API_35, Pixel_9a | `emulator -list-avds` | 0 |

`ANDROID_HOME` must be set to `~/Library/Android/sdk` for Gradle and ADB to resolve the SDK automatically. Add it to `.claude/settings.local.json` or the shell profile before running Android tasks.

## Derived configuration

| Item | Value | Rationale |
|---|---|---|
| Server port | 8000 | FastAPI/uvicorn default; injectable via config |
| Server host (general) | `127.0.0.1` | loopback; injected, never hard-coded |
| iOS simulator host | `127.0.0.1` | simulator shares host network |
| Android emulator host | `10.0.2.2` | emulator virtual router; documented in `android/AGENTS.md` |
| Swift runner data dir | per-run temp dir (e.g. `$TMPDIR/messaging-swift-<run-id>`) | isolates test instances |
| Kotlin runner data dir | per-run temp dir (e.g. `/tmp/messaging-kotlin-<run-id>`) | isolates test instances |

## Gaps

- `ANDROID_HOME` not set: add `"ANDROID_HOME": "/Users/rajpatel/Library/Android/sdk"` to `.claude/settings.local.json` `env` block, or export it in shell profile.
- Xcode not installed: N01 is `blocked`. Install Xcode from the App Store and run `sudo xcode-select -s /Applications/Xcode.app` to unblock native iOS builds and `xcrun simctl`.
- No `requirements.txt` yet: Python package versions unresolved until B01.
- Gradle wrapper not yet committed: `./gradlew` will not work until A02 creates `android/gradlew`.
- JDK 22 is newer than what Gradle 8.x typically documents as tested; if Gradle wrapper reports a version warning, pin the JDK via `JAVA_HOME` or a toolchain block in `build.gradle.kts`.
