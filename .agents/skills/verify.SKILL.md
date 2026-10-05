---
name: verify
description: Verify generated Spec_drive clients by building both platforms, running unit tests and cross-client scenarios, and recording conformance evidence after client generation.
---

# Skill: Verifier

Invoked as `/verify` in Claude Code. Runs the Verifier role defined in `AGENTS.md`.

## What this skill does

Builds both clients, runs their unit tests, runs every cross-client scenario against the real server in both role assignments, and records the result of each check. It cannot edit code, spec, or tests. Failures route back to the right role.

## Prerequisites

Before running this skill:
1. `/generate-ios` and `/generate-android` have completed.
2. The server is running (`cd server && uvicorn app.main:app`).
3. Both headless runners are built.

## Instructions

You are acting as the Verifier. Follow `AGENTS.md` - Verifier role - exactly. You MUST NOT edit client code, the server, `spec/`, or test expectations to make a check pass.

### Step 1 - build both clients

Run in `clients/ios/`:
```bash
swift build
swift test
```

Run in `clients/android/`:
```bash
./gradlew :core:test :http:test :store:test
./gradlew :runner:installDist
```

Record each as PASS, FAIL, or NOT RUN with the exact command, working directory, and exit status. A missing toolchain is NOT RUN, never PASS.

### Step 2 - start a fresh server

```bash
cd server
uvicorn app.main:app --reload
```

Confirm the server responds to `GET http://127.0.0.1:8000/v1/meta`.

### Step 3 - run validation fixtures

The following cases MUST be classified identically by both clients and the server. Test each manually or through the runner's `identify` and `send` commands, or through server unit tests (`spec/test.md` section 6):

**Usernames:**
- `"  Alice\n"` → `alice`
- `"BOB_99"` → `bob_99`
- `"Kate"` (Kelvin sign) → invalid (MUST NOT become `kate`)
- `"Ālice"` → invalid
- `a × 33` → invalid

**`message.text`:**
- `""` → invalid
- `" "` → valid, preserved
- `"é"` → valid, not normalized to `"é"`
- `👋 × 1024` (4096 bytes) → valid
- `👋 × 1025` (4100 bytes) → invalid

Record each fixture result as PASS (all three agree) or FAIL (disagreement, with which system differed and how).

### Step 4 - run cross-client scenarios

For each scenario in `spec/test.md` section 5, run it twice: once with the Swift runner as Alice and the Kotlin runner as Bob, then swapped. Use the step vocabulary exactly as defined in `spec/test.md` section 3.

Required scenarios:
- **S1:** Independent offline clients (assignment scenario)
- **S2:** Lost acknowledgement
- **S3:** Lost pull response
- **S4:** Queue survives restart
- **S5:** Server restart (if implemented; otherwise record as NOT RUN with note)

For each run, record:
- Scenario ID and role assignment (e.g. `S1 Swift=Alice Kotlin=Bob`)
- Client and server revisions (git commit)
- Exact command and working directory
- Exit status
- Pass/fail for each `Then` assertion (cite the rule ID it tests)
- Runner transcripts (stdout/stderr) attached or linked

### Step 5 - run client-only checks

These require injected transport or pages; run as unit tests if generated, otherwise NOT RUN:
- Unknown event type stored, cursor advances, sync continues (P3.5)
- Invalid page (wrong recipient, non-increasing seq, bad cursor) commits nothing and enters `protocol_error` (P7.3)
- Mismatched acknowledgement enters `protocol_error` (P5.5)
- Enqueue while submission in flight (O2.5)
- Concurrent sync triggers produce one cycle (O6.1); cancelled cycle results not committed (O6.3)

### Step 6 - native checks

Build and launch each app on a simulator or emulator. Manually verify:
- Identify screen appears with no saved identity
- Sending a message shows it as `queued`, then `accepted` after sync
- Going offline, sending, reconnecting flushes the queue
- App relaunch with data intact shows previous messages

Record each as PASS, FAIL, or NOT RUN (a missing simulator/emulator is NOT RUN, never PASS).

### Step 7 - route failures

For each failure, identify the rule ID and route it:
- Client violates a clear rule → back to that platform's Implementer (W2 with the rule ID and observed behavior)
- Spec is ambiguous, contradictory, or wrong → to the Analyzer (W1 with the conflicting files and rules)
- Server or harness is wrong → W4

### Step 8 - record evidence and handoff

Update task X01 in `.agents/TASKS.md` with one entry per check:
```
S1 Swift=Alice Kotlin=Bob | PASS | swift build 0 | ./gradlew :runner:installDist 0 | pytest -k S1 0
```

End with:
- Role: Verifier
- Summary: X passed, Y failed, Z not run (total checks)
- Failures: each with rule ID, scenario, expected, observed
- Blockers: anything that prevents further verification
- A headless pass does NOT prove the native app works; both are required
