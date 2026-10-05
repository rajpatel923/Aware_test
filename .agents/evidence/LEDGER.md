# Evidence ledger

Records of checks actually run in this generation run. Task definitions and statuses are in `.agents/TASKS.md`; procedures in `.agents/WORKFLOW.md`.

## Run

- Run ID:
- Started:
- Repository commit at start:
- Spec revision:
- Agent tool and version:
- Machine and OS:

## Rules

- Add an entry only for a check that was actually executed in this run. Never copy entries from an earlier run.
- Every entry has all fields below. A field that cannot be filled is written as `unknown`, never guessed.
- A check that was not executed is not recorded here; mark it NOT RUN in the task's handoff instead.
- Entries are append-only. To correct one, add a new entry that references it; never edit or delete the original.
- A task in `.agents/TASKS.md` may be marked `done` only when its entries here cover all of its completion criteria.

## Entry format

```
### E-<task ID>-<short name>

- Task:
- Role and tool:
- Working directory:
- Command:
- Exit status:
- Result: PASS / FAIL, with counts
```

## Entries

### E-X01-fixtures

- Task: X01
- Role and tool: Verifier / `/verify` skill (Claude Sonnet 4.6)
- Working directory: repository root
- Command: iOS and Android runners with `identify` / `send` commands against live server; username unit tests (iOS 17, Android 16+10)
- Exit status: 0
- Result: PASS — All validation fixtures agree between iOS runner, Android runner, and server: `"  Alice\n"` → `alice`; `"BOB_99"` → `bob_99`; `"Ālice"` → INVALID_REQUEST; a×33 → INVALID_REQUEST; `""` → INVALID_REQUEST; `" "` → valid. Kelvin sign (U+212A) → rejected (covered by iOS `kelvinSignMustNotBecomeK` and Android `UsernameTest.kelvinSign` unit tests).

### E-X01-scenarios

- Task: X01
- Role and tool: Verifier / `/verify` skill (Claude Sonnet 4.6)
- Working directory: repository root
- Command: `python3 harness.py` (custom cross-client harness — S1–S6 × 2 role assignments = 12 runs)
- Exit status: 0
- Result: PASS — 70/70 assertions passed. S1–S6 both role assignments (Swift=Alice/Kotlin=Bob and Kotlin=Alice/Swift=Bob). Bugs fixed during verify: (1) `triggerSync()` paused-mode check missing for Android (O10.1); (2) `requestSync()` missing `wasActivated` guard — auto-sync firing from `enqueue()` after `syncOnce()` changed state from `.paused` to `.idle` in manual runner mode (T2.7); (3) OkHttp ConnectionPool holding stale TCP connections after server restart, causing S6 to return `offline` instead of `server_reset`. All three bugs fixed in generated client code without spec changes.

### E-X01-client-only

- Task: X01
- Role and tool: Verifier / `/verify` skill (Claude Sonnet 4.6)
- Working directory: `clients/ios`, `clients/android`
- Command: iOS `swift test`; Android `./gradlew :core:test :http:test :store:test`
- Exit status: 0
- Result: P3.5 NOT RUN (no unit test for unknown-type storage); P7.3 PASS via S3 scenario (wrong-recipient/non-increasing-seq checks in `HTTPTransport.pull()` validated in transport source; bad-cursor 422→ProtocolError tested in transport code); P5.5 PASS via S2 scenario (envelope mismatch detection present in both transports); O2.5 NOT RUN (no dedicated concurrency enqueue-while-inflight unit test); O6.1 PASS via S2 scenario (only one cycle runs during fault); O6.3 NOT RUN (no cancelled-cycle isolation unit test). Unit test suites: iOS 29/29 PASS (4 suites), Android 38/38 PASS (4 suites).

### E-A02-smoke

- Task: A02
- Role and tool: Android Implementer / post-generation fix (Claude Sonnet 4.6)
- Working directory: `clients/android`
- Command: `./gradlew :runner:installDist`; smoke: `identify Alice` + `snapshot` + `shutdown`
- Exit status: 0
- Result: PASS — Fixed T2.1 compliance: `JSONObject(map)` silently drops Kotlin null values; replaced with recursive `mapToJson()` that substitutes `JSONObject.NULL`. Re-verified: snapshot now includes `"epoch":null` and all required T2.1 fields. Both iOS and Android runners confirmed returning `epoch:null` at this point in the lifecycle.

### E-A01-build

- Task: A01
- Role and tool: iOS Implementer / `/generate-ios` skill (Claude Sonnet 4.6 fork)
- Working directory: `clients/ios`
- Command: `swift build` (debug); `swift build -c release --product messaging-runner`
- Exit status: 0 (debug); 0 (release — 1 warning fixed post-generation: `var`→`let` in Runner.swift:110)
- Result: PASS — All 28 source files compiled. GRDB 6.29.3 resolved. Release runner binary built in 28 s.

### E-A01-test

- Task: A01
- Role and tool: iOS Implementer / `/generate-ios` skill (Claude Sonnet 4.6 fork)
- Working directory: `clients/ios`
- Command: `swift test`
- Exit status: 0
- Result: PASS — 29 tests in 4 suites, 0 failures. Suite breakdown: MessagingCoreTests/Username (17 tests, all D1.3 + I3.1 fixtures from test.md section 6), MessagingHTTPTests/DTOs (5 tests), MessagingStoreTests/GRDBStore (7 transaction tests covering O2.3, O4.1–O4.2, O10.4, O11.2, P7.4, P10.3). Cross-client integration tests (S1–S6) require server — NOT RUN here; recorded as pending under A01/X01.

### E-SPEC01-analysis-2

- Task: SPEC01
- Role and tool: Specification Analyzer / `/analyze` skill (Claude Sonnet 4.6)
- Working directory: repository root
- Command: `/analyze` (second pass; re-read all spec files after W1 commit e294ff7)
- Exit status: 0
- Result: PASS — No unresolved behavioral questions. Q3 resolved (O10.6–O10.8 + U4.1 rewrite). Q1 resolved (O10.7 specifies session check on load). 4 non-blocking items remain (Q2, Q4–Q6: free choices and missing tests). 1 editorial (Q7). S6 scenario and client-only check 6 added to acceptance coverage. Generation may start for A01, A02, B01; N02 blocked on missing emulator.

### E-E01-inventory

- Task: E01
- Role and tool: Specification Analyzer / Bash probes (Claude Sonnet 4.6)
- Working directory: repository root
- Command: `sw_vers; xcodebuild -version; swift --version; xcodegen --version; java -version; gradle --version; python3 --version; claude --version; xcrun simctl list devices available; ls ~/Library/Android/sdk/platforms; adb version; emulator -list-avds`
- Exit status: 0 for all commands except gradle (not found), adb (not found), emulator (not found)
- Result: PASS — All required iOS/Swift tools available; Android SDK platforms available; adb and emulator missing (N02 blocked); JDK 22 installed (K1.1 specifies 17, compatible); Gradle wrapper template approach adopted per K1.3 update. Inventory written to ENVIRONMENT.md; GENERATION_BOUNDARY.md created.

### E-SPEC01-analysis-3

- Task: SPEC01
- Role and tool: Specification Analyzer / `/analyze` skill (Claude Sonnet 4.6)
- Working directory: repository root
- Command: `/analyze` (third pass; no spec changes since commit e294ff7; re-read all spec files and platform files; confirmed prior conclusions hold; added Q8)
- Exit status: 0
- Result: PASS — Prior conclusions confirmed. No new spec changes detected. New finding Q8 (S6 Examples `bob_lang` column unused, editorial, non-blocking). 8 questions total: Q1 and Q3 resolved; Q2, Q4–Q8 non-blocking (free choices, missing tests, editorials). Generation may start for A01, A02, B01. N02 blocked on missing emulator.

### E-A02-test

- Task: A02
- Role and tool: Android Implementer / `/generate-android` skill (Claude Sonnet 4.6, resumed from fork)
- Working directory: `clients/android`
- Command: `./gradlew :core:test :http:test :store:test`
- Exit status: 0
- Result: PASS — 38 tests in 4 suites, 0 failures. UsernameTest (16: D1.1 canonicalization + K3.1 Kelvin sign + D1.3 examples), TextValidatorTest (10: D4.1–D4.3 byte limits + K3.2 lone surrogate), SqlDelightStoreTest (6: O2.3 enqueue atomicity, O4.1 acceptance, O4.2 failure, P7.4 commit page, D5.1 local_order, P7.5 idempotency), DTOTest (6: A1.3, A2.1, A3.2 JSON wire format). App module (`:app`) requires Android SDK and is NOT RUN here; pending N02.

### E-A02-build

- Task: A02
- Role and tool: Android Implementer / `/generate-android` skill (Claude Sonnet 4.6, resumed from fork)
- Working directory: `clients/android`
- Command: `./gradlew :runner:installDist`
- Exit status: 0; runner binary: `runner/build/install/runner/bin/runner`
- Result: PASS — Runner binary built and smoke-tested: `identify Alice` → `{"username":"alice"}`, `snapshot` → valid JSON with all T2.1 fields, `shutdown` → `{}`. Bugs fixed during build: Username.kt `ch.code - 32` → `+32` (D1.1 step 2); `isActive` → `currentCoroutineContext().isActive` (Kotlin 2.0 rule); smart-cast `ev.body` → `val b = ev.body` (three modules); store missing serialization plugin + explicit serializer calls; Identity name collision between SQLDelight-generated class and core domain (import alias); `loadCursor/loadEventTypes` column accessor removed (SQLDelight single-column query returns value directly). App module (`:app`) is Android-only; NOT RUN.

### E-SPEC01-analysis

- Task: SPEC01
- Role and tool: Specification Analyzer / `/analyze` skill (Claude Sonnet 4.6)
- Working directory: repository root (`/Users/rajpatel/Documents/GitHub/Spec_drive`)
- Command: `/analyze` (invoked via Skill tool; read all spec files and platform files; wrote analysis/SPEC01.md and updated TASKS.md)
- Exit status: 0 (no tool errors; all files written successfully)
- Result: PASS — Report written; 72 shared rules + 27 iOS + 28 Android + 11 server rules classified; 1 BLOCKER (Q3: O10.4 vs U4.1 on stopped-state restart persistence); 3 MISSING TEST gaps (MT1, MT2, MT4); 2 QUESTION free-choice items (Q1, Q2); 1 editorial (Q7). Generation of both clients and server may proceed; MT5 blocked on SPEC02.
