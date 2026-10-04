# Test Specification

Status: draft, protocol version 1.

This file defines how conformance is proven: the headless runner contract every client implements, a fixed step vocabulary, the required scenarios, and validation fixtures. Expected results here are the oracle. They MUST NOT be edited to make failing code pass; change them only together with the spec rule they test. Rules carry IDs (`T…`).

## 1. Test levels

- **Fixtures:** both clients and the server classify the cases in section 6 identically.
- **Client unit:** each client's core, with injected transport, clock, and ID source.
- **Server:** idempotency, conflicts, paging, epochs, validation (`protocol.md` sections 6–7).
- **Cross-client:** the scenarios in section 5, run with real clients against the real server over HTTP.
- **Native:** each app builds, launches, and completes scenario S1's flow manually or through UI tests.

T1.1 Cross-client scenarios MUST use one client of each language. Two instances of the same client, or fake in-memory clients, do not count.

T1.2 Every scenario MUST pass twice per run: once with the Swift client as Alice and the Kotlin client as Bob, and once swapped.

T1.3 A headless pass does not prove the native app works, and vice versa.

## 2. Headless runner contract

Each client provides a headless runner built from the same core as its app. The test harness drives it through JSON Lines on stdin and stdout. Logs go to stderr only.

Request: `{"id": "7", "cmd": "send", "args": {"recipient": "bob", "type": "message.text", "body": {"text": "hi"}}}`
Success: `{"id": "7", "ok": true, "result": {...}}`
Failure: `{"id": "7", "ok": false, "error": {"code": "...", "message": "..."}}`

| Command | Args | Result |
|---|---|---|
| `identify` | `name` | `username` |
| `send` | `recipient`, `type`, `body` | `event_id`, `status` |
| `network` | `online` (bool) | `online` |
| `sync_once` | none | `state`, `pulled`, `accepted`, `failed`, `pending` |
| `snapshot` | none | `username`, `epoch`, `cursor`, `state`, `outbox`, `events` |
| `fault` | `drop_next_response`: `submit` or `pull` | `armed` |
| `reset_session` | none | `epoch`, `cursor` |
| `shutdown` | none | `{}` |

T2.1 Each entry in `events` has every `domain.md` local-event field: `event_id`, `type`, `sender`, `recipient`, `body`, `seq`, `accepted_at`, `direction`, `status`, `local_order`, `failure_code`, `epoch`. `outbox` lists `event_id`s in `local_order`.

T2.2 `state` is one of the sync states in `offline-behavior.md` section 7.

T2.3 `network {"online": false}` closes the client's transport gate. Requests then fail as connection errors, which the client MUST treat exactly like real network loss (`offline-behavior.md` O1.2).

T2.4 `fault` makes the transport discard the next matching response after the server has processed the request, then report a timeout. It lives in the runner's transport wrapper, never in messaging logic.

T2.5 Runners start in manual mode (`offline-behavior.md` O10.1). Start-up options are base URL and data directory; exact flags are defined in `platform/ios.md` and `platform/android.md`.

T2.7 `sync_once` runs exactly one cycle immediately, ignoring backoff and poll delays, and returns the state the cycle ended in: `idle`, `syncing` (more work remains), `offline`, or an error state. It never returns `paused`.

T2.6 A runner restarted with the same data directory MUST resume from its stored state.

## 3. Step vocabulary

Scenarios are standard Gherkin (`Feature`, `Scenario Outline`, `Examples`), so an off-the-shelf runner such as pytest-bdd can parse them. Every scenario is an outline over the two role assignments in T1.2. Scenarios use only these steps. Each maps to runner commands, so the harness executes scenarios without hand-written step code. New features add new steps here.

- `a fresh server` — start a new server process (new epoch).
- `<User>'s client is <language> with empty storage` — start a runner with a new data directory.
- `<User> identifies as "<name>"` → `identify`.
- `<User> sends "<text>" to "<username>" as <ref>` → `send` with type `message.text`; bind `event_id` to `<ref>`.
- `<User> goes offline` / `goes online` → `network`.
- `<User> syncs` → `sync_once`, repeated while `state` is `syncing`, at most 10 times. The step fails if the client is still `syncing` after 10 cycles, or ends in an error state the scenario did not expect.
- `<User> restarts` → `shutdown`, then start with the same data directory.
- `the server restarts` — stop the current server process and start a new one; new epoch, `seq` from 1, empty mailboxes, no event keys (`protocol.md` P10.1).
- `<User> resets session` → `reset_session`; the client adopts the new epoch and sets cursor to 0 in one transaction (`protocol.md` P10.3).
- `the next <submit|pull> response to <User> is lost` → `fault`.
- `Then` steps → `snapshot`, then compare as below.

T3.1 Assertions on snapshots:
- `<User> holds <ref> once from "<sender>" with text "<text>" as <status>`: exactly one event with that `event_id`; sender, text, and status equal byte for byte.
- `<ref> is <status> on <User>`: the event's `status` equals.
- `<User> does not hold <ref>`.
- `<User>'s outbox is empty` / `contains <ref>`.
- `<User>'s conversation with "<peer>" is <ref>, <ref>, …`: those events in display order (`protocol.md` P8.2), and no others.
- `<User>'s state is <state>`.

T3.2 Event IDs, `seq`, `accepted_at`, and epochs are never compared to literal values; refer to them through bound refs.

T3.3 Time never appears in a scenario. No step sleeps.

## 4. Pass criteria

T4.1 A scenario passes only if every assertion passes in both role assignments (T1.2).

T4.2 Each run records: scenario ID, role assignment, client and server revisions, toolchain versions, exact command, exit status, and the runner transcripts.

## 5. Required scenarios

### S1: Independent offline clients (assignment scenario)

```gherkin
Feature: Messaging conformance

Scenario Outline: Independent offline clients
  Given a fresh server
  And Alice's client is <alice_lang> with empty storage
  And Bob's client is <bob_lang> with empty storage

  When Alice identifies as "Alice"
  And Bob identifies as "Bob"

  # Assignment step 1
  When Alice sends "Hi Bob, I have something important to tell you" to "bob" as m1
  And Alice syncs
  Then m1 is accepted on Alice
  When Bob syncs
  Then Bob holds m1 once from "alice" with text "Hi Bob, I have something important to tell you" as received

  # Assignment step 2
  When Bob sends "What is it?" to "alice" as m2
  And Bob syncs
  And Alice syncs
  Then Alice holds m2 once from "bob" with text "What is it?" as received

  # Assignment step 3
  When Alice goes offline
  And Alice sends "The answer is 42" to "bob" as m3
  And Alice syncs
  Then m3 is queued on Alice
  And Alice's outbox contains m3
  And Alice's state is offline

  # Assignment step 4
  When Bob goes offline
  And Bob sends "Are you there?" to "alice" as m4
  And Bob syncs
  Then m4 is queued on Bob
  And Bob's outbox contains m4

  # Assignment step 5
  When Alice goes online
  And Alice syncs
  Then m3 is accepted on Alice
  And Alice's outbox is empty
  And Alice does not hold m4

  # Assignment step 6
  When Alice goes offline

  # Assignment step 7
  When Bob goes online
  And Bob syncs
  Then Bob holds m3 once from "alice" with text "The answer is 42" as received
  And m4 is accepted on Bob
  And Bob's outbox is empty
  And Alice does not hold m4

  # Beyond the assignment: eventual receipt and identical views
  When Alice goes online
  And Alice syncs
  Then Alice holds m4 once from "bob" with text "Are you there?" as received
  And Alice's conversation with "bob" is m1, m2, m3, m4
  And Bob's conversation with "alice" is m1, m2, m3, m4

  Examples:
    | alice_lang | bob_lang |
    | swift      | kotlin   |
    | kotlin     | swift    |
```

The texts for m3 and m4 are not given by the assignment; any valid text works. Syncing while offline in steps 3 and 4 is deliberate: it proves a failed sync keeps the event queued.

### S2: Lost acknowledgement

```gherkin
Feature: Messaging conformance

Scenario Outline: Lost acknowledgement
  Given a fresh server
  And Alice's client is <alice_lang> with empty storage
  And Bob's client is <bob_lang> with empty storage
  When Alice identifies as "alice"
  And Bob identifies as "bob"
  And Alice sends "Sent once" to "bob" as m1
  And the next submit response to Alice is lost
  And Alice syncs
  Then m1 is queued on Alice
  When Alice syncs
  Then m1 is accepted on Alice
  When Bob syncs
  Then Bob holds m1 once from "alice" with text "Sent once" as received

  Examples:
    | alice_lang | bob_lang |
    | swift      | kotlin   |
    | kotlin     | swift    |
```

Proves `protocol.md` P5.3, P5.4, and P6.1: the retry reuses the ID, and the server stores the event once.

### S3: Lost pull response

```gherkin
Feature: Messaging conformance

Scenario Outline: Lost pull response
  Given a fresh server
  And Alice's client is <alice_lang> with empty storage
  And Bob's client is <bob_lang> with empty storage
  When Alice identifies as "alice"
  And Bob identifies as "bob"
  And Alice sends "Pulled twice" to "bob" as m1
  And Alice syncs
  And the next pull response to Bob is lost
  And Bob syncs
  Then Bob does not hold m1
  When Bob syncs
  Then Bob holds m1 once from "alice" with text "Pulled twice" as received

  Examples:
    | alice_lang | bob_lang |
    | swift      | kotlin   |
    | kotlin     | swift    |
```

Proves `protocol.md` P6.5 and P7.4–P7.5.

### S4: Queue survives restart

```gherkin
Feature: Messaging conformance

Scenario Outline: Queue survives restart
  Given a fresh server
  And Alice's client is <alice_lang> with empty storage
  And Bob's client is <bob_lang> with empty storage
  When Alice identifies as "alice"
  And Bob identifies as "bob"
  And Alice goes offline
  And Alice sends "Survives restart" to "bob" as m1
  And Alice restarts
  Then m1 is queued on Alice
  When Alice goes online
  And Alice syncs
  And Bob syncs
  Then Bob holds m1 once from "alice" with text "Survives restart" as received

  Examples:
    | alice_lang | bob_lang |
    | swift      | kotlin   |
    | kotlin     | swift    |
```

Proves `offline-behavior.md` O3.1 and O10.4.

### S5: Server restart and recovery

```gherkin
Feature: Messaging conformance

Scenario Outline: Server restart and recovery
  Given a fresh server
  And Alice's client is <alice_lang> with empty storage
  And Bob's client is <bob_lang> with empty storage
  When Alice identifies as "alice"
  And Bob identifies as "bob"

  # Establish pre-restart state
  When Alice sends "Before restart" to "bob" as m1
  And Alice syncs
  And Bob syncs
  Then m1 is accepted on Alice
  And Bob holds m1 once from "alice" with text "Before restart" as received

  # Queue a message; restart the server before it can be submitted
  When Alice sends "After restart" to "bob" as m2
  And the server restarts
  And Alice syncs
  Then Alice's state is server_reset
  And Alice holds m1 once from "alice" with text "Before restart" as accepted
  And m2 is queued on Alice
  And Alice's outbox contains m2

  # Recovery: Alice adopts new epoch, resubmits outbox
  When Alice resets session
  And Alice syncs
  Then m2 is accepted on Alice
  And Alice's outbox is empty

  # Bob recovers and receives m2 (m1 is gone from the server; Bob holds it locally only)
  When Bob resets session
  And Bob syncs
  Then Bob holds m2 once from "alice" with text "After restart" as received

  Examples:
    | alice_lang | bob_lang |
    | swift      | kotlin   |
    | kotlin     | swift    |
```

Proves `protocol.md` P10.1–P10.3 and `offline-behavior.md` O9.1–O9.2: the client enters `server_reset`, keeps all local data, resubmits the outbox with original envelopes after recovery, and never reuses the old cursor.

## 6. Validation fixtures

Every case MUST be classified identically by the server and both clients. Long strings are written as `<char> × <count>`.

**Usernames** (`domain.md` D1):

| Input | Expected |
|---|---|
| `"  Alice\n"` | `alice` |
| `"BOB_99"` | `bob_99` |
| `"\talice\r"` | `alice` |
| `a × 32` | valid, unchanged |
| `""`, `"   "` | invalid |
| `"al ice"`, `"al-ice"`, `"alice!"` | invalid |
| `"Ālice"`, `"İstanbul"` | invalid |
| `"\u00A0alice"` | invalid |
| `"\u212Aate"` (Kelvin sign K) | invalid; MUST NOT become `kate` |
| `a × 33` | invalid |

**`message.text`** (`domain.md` D4):

| Input | UTF-8 bytes | Expected |
|---|---|---|
| `"hi"` | 2 | valid |
| `""` | 0 | invalid |
| `" "` | 1 | valid, preserved |
| `"  padded  "` | 10 | valid, preserved |
| `"e\u0301"` | 3 | valid, not normalized |
| `"👋"` | 4 | valid |
| `a × 4096` | 4096 | valid |
| `a × 4097` | 4097 | invalid |
| `👋 × 1024` | 4096 | valid |
| `👋 × 1025` | 4100 | invalid |
| lone surrogate (JSON `"\ud800"`) | n/a | invalid (server test only) |

Valid text MUST round-trip from sender to recipient byte for byte.

## 7. Client-only checks

These cannot be produced through the cross-client harness and are covered by client unit tests with injected pages or transports:

- An incoming event of an unknown type is stored, advances the cursor, and does not stop sync (`protocol.md` P3.5).
- An invalid page (wrong recipient, non-increasing `seq`, bad cursor) commits nothing and enters `protocol_error` (P7.3).
- A mismatched acknowledgement enters `protocol_error` (P5.5).
- Enqueue succeeds while a submission is in flight (`offline-behavior.md` O2.5).
- Concurrent sync triggers run one cycle (O6.1); results from a cancelled cycle are not committed (O6.3).