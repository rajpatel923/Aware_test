## Chat app at a glance
Summary only. `AGENTS.md` and `spec/` are authoritative; if this section disagrees with them, they win and this section must be corrected.

A local messaging app: one Python/FastAPI server and two independent clients, Swift (iOS) and Kotlin (Android), that must behave identically.

What the app must do:
- Identify the user by name on first launch.
- Send text addressed to another user.
- Queue messages locally while offline and flush them on reconnect.
- Display messages received from the server.

| Part | Stack | Location |
|---|---|---|
| Server | Python, FastAPI, single process, in-memory mailboxes | `backend/` |
| iOS client | Swift core, SwiftUI, URLSession, SQLite via GRDB, headless runner | `ios/` |
| Android client | Kotlin core, Compose, OkHttp, SQLite via SQLDelight, headless JVM runner | `android/` |
| Contract | Behavior rules, HTTP schema, shared test scenarios | `spec/` |

Hard limits: runs fully locally, no hosted services, no messaging SDKs, no shared messaging code between Swift and Kotlin, and never hard-code the test conversation into the app. Key trap: when Bob sends his message in step 5 of the Alice/Bob scenario, offline Alice has NOT received it yet.

## Claude-specific notes

### Before editing
Read the task entry in `.agent/task.md`, the `spec/` sections it references, and the relevant
`.agent/design.md` section. Then read the platform file for each folder you touch -
`backend/AGENTS.md`, `ios/AGENTS.md`, or `android/AGENTS.md` - before making any edits. These
are not loaded automatically; open them explicitly.

### Verification honesty
- A headless pass does not prove a native build or lifecycle correctness. State which one you ran.
- Mark a task complete in `.agent/task.md` only when its acceptance evidence (command + exit
  status) exists in this session.

### Session start
If `/context` does not list `AGENTS.md` under memory files, read it manually before doing anything else.