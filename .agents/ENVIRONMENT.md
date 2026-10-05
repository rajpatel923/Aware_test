# E01 - Environment inventory

Probed 2026-10-05. Working directory: repository root.

## Inventory

| Item | Status | Version / Detail                                                               |
|---|---|--------------------------------------------------------------------------------|
| macOS | available | 27.2 (Build 26B5091g)                                                          |
| Xcode | available | 27.0 (Build 27A266a)                                                           |
| Swift | available | 6.4 (swiftlang-6.4.0.34.1, clang-2100.3.34.1)                                  |
| XcodeGen | available | 2.46.0                                                                         |
| Python 3 | available | 3.12.9                                                                         |
| Claude Code | available | 2.1.190                                                                        |
| OpenJDK | available | 22 (build 22+36-2370) - see note                                               |
| Gradle (system) | missing | Not installed system-wide; not required |
| Android SDK | available | Platforms: android-34, android-35, android-37.0                                |
| `adb` | missing | Not on PATH                                                                    |
| Android emulator | missing | Not on PATH; no AVDs listed                                                    |

**JDK note:** `spec/platform/android.md` K1.1 specifies JDK 17; JDK 22 is installed. JDK 22 is backward-compatible for Kotlin/Gradle use; Gradle 8.x supports JDK 22. Generation may proceed with JDK 22. Update K1.1 in a separate spec task if a strict version bound is needed.

## iOS simulators (available)

| Device | UDID | State |
|---|---|---|
| iPhone 17 | 57FBCF3C-61E8-4584-AD76-D3C69BA32129 | Booted |
| iPhone 17 Pro Max | 3F27C7B8-EC97-4740-BCF9-3BFAD2B28E71 | Shutdown |
| iPhone 18 Pro Max | C3A60E6A-C9C9-4D12-A137-9D0FD4CD20A8 | Shutdown |
| iPhone 17e | 4E6245C4-5A6E-4C44-BDE2-6DC6A1135288 | Shutdown |
| iPhone Air | 7E47A779-9B9D-4442-A92C-63819D0A23A1 | Shutdown |
| iPad Pro 13-inch (M5) | 0A889466-8794-4DCD-9492-80061C663402 | Shutdown |

**Default simulator for N01:** iPhone 17 (already Booted).

## Android emulator / device

`adb` and `emulator` are not on PATH. No AVDs found. Native app testing (N02) is `blocked` until a configured emulator or physical device is available. Cross-client headless testing (A02) runs on the JVM and is not blocked.

## Simulator / emulator connectivity

- iOS simulator reaches the host Mac at `127.0.0.1` (matches `platform/ios.md` I7.3 default `http://127.0.0.1:8000`). Connectivity not yet verified against a running server.
- Android emulator would reach the host at `10.0.2.2` (matches `platform/android.md` K7.3); untested - no emulator available.

## Probe commands used

```sh
sw_vers
xcodebuild -version
swift --version
xcodegen --version
java -version
gradle --version        
python3 --version
claude --version
xcrun simctl list devices available
ls ~/Library/Android/sdk/platforms
adb version               # → not found
emulator -list-avds       # → not found
```

All commands run from repository root on 2026-10-05.
