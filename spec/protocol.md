# Messaging Protocol


This file defines how clients and the server exchange messages: the event envelope, how new event types are added, idempotent submission, sequencing, cursors, server sessions, and delivery guarantees. It is transport-independent and normative. Rules carry stable IDs (`P5.2`) so generated code, tests, and reviews can cite them.

**Owned elsewhere:** endpoints, HTTP status codes, and JSON wire shapes are in `api.md`. Usernames, text rules, and entities are in `domain.md`. The client outbox, sync loop, retry timing, and connectivity are in `offline-behavior.md`. Display is in `ui.md`. Scenarios and fixtures are in `test.md`. If this file conflicts with another spec file, report the conflict; do not pick one.

MUST, MUST NOT, SHOULD, and MAY carry their usual requirement meanings. Items marked **[DECISION NEEDED]** are proposals awaiting confirmation.

## 1. Model

Every user has a mailbox on the server: an ordered log of events addressed to them. Clients do two things only:
- **Submit** an event they created, identified by an ID they chose.
- **Pull** events from their own mailbox that come after a cursor they keep.

The server assigns each accepted event a sequence number. Clients never push to each other directly, and the server never pushes to clients. Everything below follows from three properties: submissions are idempotent, sequences define order, and cursors only advance after a successful local commit.

## 2. Event envelope

P2.1 Every event, of every type, uses this envelope:

| Field | Set by | Meaning |
|---|---|---|
| `event_id` | client | Lowercase hyphenated UUID, generated once when the event is created |
| `type` | client | Event type name (section 3) |
| `sender` | client | Canonical username of the author (`domain.md`) |
| `recipient` | client | Canonical username of the mailbox owner |
| `body` | client | JSON object whose schema is defined by `type` |
| `seq` | server | Positive integer assigned at acceptance |
| `accepted_at` | server | UTC acceptance time, millisecond precision; display only |

P2.2 The **event key** is `(sender, event_id)`. It identifies one logical event for the whole server session.

P2.3 `event_id`, `type`, `sender`, `recipient`, and `body` are immutable after creation. Retries MUST resend them unchanged.

P2.4 `seq` and `accepted_at` MUST NOT be used by a client before the server returns them, and MUST NOT be invented locally.

P2.5 Envelope fields are fixed for protocol version 1. Adding or changing an envelope field is a protocol version change (P4.3). New behavior is added through new types and their bodies.

## 3. Event types and extension

P3.1 Version 1 defines one type:

| Type | Body | Defined in | Since |
|---|---|---|---|
| `message.text` | `{ "text": string }` | `domain.md` (text rules) | v1 |

P3.2 Type names are lowercase `<feature>.<action>` (pattern `^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$`). A name is never reused for a different body.

P3.3 The server MUST advertise the types it accepts (P4.1). It MUST reject a submission whose type it does not support, with `UNSUPPORTED_TYPE`, and store nothing.

P3.4 A client MUST only submit types the server advertises, except `message.text`, which every v1 server supports and which a client may enqueue before it has ever contacted a server. If any other type is not in the last saved metadata, the client MUST refuse it locally before enqueueing (`offline-behavior.md` O2.2).

P3.5 A client that pulls an event with a type it does not understand MUST store it, advance its cursor normally, and never fail or stall sync because of it. It SHOULD show a neutral placeholder (`ui.md`). This lets newer clients and older clients share a server.

P3.6 A body that does not match its type's schema is invalid. The server rejects it with `INVALID_REQUEST`. A client that pulls one treats the page as a protocol error (P7.3).

P3.7 An event that refers to an earlier event (for example a reaction or an edit) MUST identify it by its event key, `(sender, event_id)`, never by `seq`, which is not stable across server sessions.

P3.8 **Adding a feature.** A new event type is added by: registering it in the P3.1 table; defining its body schema and validation in the owning spec file; defining its display in `ui.md`; and adding scenarios to `test.md`. If the envelope, ordering, or addressing rules in this file stay the same, the change is additive and keeps protocol version 1.

P3.9 **Changes that need a new protocol version:** any envelope change, a new kind of recipient (for example group conversations, which need membership and a different mailbox addressing model), or any change to sections 5–8. These MUST be specified here before any client code changes.

## 4. Session and versioning

P4.1 The server exposes metadata: `protocol_version` (integer), `server_epoch` (opaque string, new at each server start), and `event_types` (list of accepted types).

P4.2 Before its first submission or pull, a client MUST fetch metadata. If `protocol_version` differs from the version the client implements, the client MUST stop syncing and report incompatibility. It MUST NOT guess.

P4.3 Protocol versions are integers. Additive event types (P3.8) do not change the version; changes in P3.9 do.

P4.4 Every submission and pull MUST carry the client's saved epoch. The server MUST reject a mismatched epoch with `SERVER_EPOCH_CHANGED` and change nothing.

## 5. Submission

P5.1 A client MUST durably store an event in its outbox before submitting it (`offline-behavior.md`).

P5.2 A client MUST have at most one submission in flight, and MUST submit in local creation order.

P5.3 A retry MUST resend the identical envelope (P2.3). A client MUST NOT create a new `event_id` for the same logical event.

P5.4 A timeout, disconnect, or cancelled request means the outcome is unknown, not that the event was rejected. The client MUST keep the outbox entry and retry.

P5.5 On a successful response, the client MUST check that the returned envelope matches its stored event exactly before recording `seq` and `accepted_at`. A mismatch is a protocol error.

P5.6 A rejection for that specific event (`INVALID_REQUEST`, `EVENT_ID_CONFLICT`, `UNSUPPORTED_TYPE`) is permanent. The client MUST mark the event failed, remove it from the outbox, and continue with the next event.

P5.7 A retryable failure on the oldest outbox entry MUST block later entries, so the server sees the sender's events in creation order.

## 6. Server acceptance

P6.1 The server MUST handle each submission as one indivisible operation:
- New event key: assign the next `seq`, record `accepted_at`, append the event to the recipient's mailbox, and return the stored envelope.
- Existing key, identical envelope: return the originally stored envelope unchanged (same `seq` and `accepted_at`) and append nothing.
- Existing key, different `type`, `recipient`, or `body`: reject with `EVENT_ID_CONFLICT` and change nothing.

P6.2 First acceptance and identical retry MUST be indistinguishable to the client.

P6.3 `seq` starts at 1 in each server session and strictly increases across all accepted events in that session, regardless of recipient. A mailbox therefore has gaps; gaps carry no meaning.

P6.4 A rejected submission MUST NOT change server state or consume a `seq`.

P6.5 The server MUST keep every accepted event and every event key for the whole session. Pulling MUST NOT remove or change events, because a pull response can be lost.

P6.6 Self-addressed events (`sender` equals `recipient`) are valid and are stored once.

## 7. Pulling

P7.1 A client pulls from its own mailbox with `after` set to its cursor. The server returns that mailbox's events with `seq > after`, in ascending `seq`, at most `limit` per page. The page also states whether more events exist and the cursor to use next (`api.md` defines field names and limits).

P7.2 A client's cursor starts at 0 for each epoch and is the highest `seq` it has committed from its own mailbox.

P7.3 Before committing a page, the client MUST verify: the epoch matches; every event's `recipient` is the client's own username; every envelope is complete and its body valid for known types; `seq` values strictly increase and exceed the requested cursor; and the returned next cursor equals the last `seq` (or the requested cursor if the page is empty). Any failure is a protocol error, and nothing from the page is committed.

P7.4 A valid page and the new cursor MUST be committed in one local transaction. If the commit fails, neither is saved and the same page is pulled again.

P7.5 An event whose key the client already holds with an identical envelope MUST NOT create a second visible event. If the client holds the same key with different content, that is a protocol error and the stored event MUST NOT be overwritten.

P7.6 If a pulled event is the client's own self-addressed event still in its outbox, the same transaction MUST record its acceptance and remove the outbox entry.

P7.7 The cursor MUST advance only through P7.4: never from a submission response, a timestamp, or a guess.

## 8. Ordering

P8.1 The authoritative order of events is ascending `seq` within a server session.

P8.2 Accepted events MUST be presented in `seq` order. A client's own events not yet accepted follow them, in local creation order (`ui.md`).

P8.3 Because acceptance order is the shared truth, an event created offline may be ordered after an event another user sent later in wall-clock time. This is intended.

## 9. Errors

Every error carries a stable `code`, a human-readable `message`, and the server epoch when known. Status codes and field names are in `api.md`.

| Code | Cause | Client action |
|---|---|---|
| `INVALID_REQUEST` | Malformed envelope, invalid username, invalid body, missing epoch | Mark that event failed (P5.6) |
| `UNSUPPORTED_TYPE` | Type not advertised by this server | Mark that event failed (P5.6) |
| `EVENT_ID_CONFLICT` | Same event key, different content | Mark that event failed (P5.6); never retry |
| `SERVER_EPOCH_CHANGED` | Saved epoch is not the server's current epoch | Enter reset handling (section 10) |
| `INVALID_CURSOR` | Cursor negative or beyond the session's highest `seq` | Stop sync; report a protocol error; never reset silently |
| Transport failure, timeout, 5xx | Outcome unknown | Keep outbox; retry later (`offline-behavior.md`) |
| Malformed or mismatched success response | Server or client bug | Stop sync; report a protocol error; treat nothing as accepted |

## 10. Server restarts

P10.1 A server restart begins a new session: new epoch, `seq` from 1, empty mailboxes, no event keys. Events accepted by the old session but not yet pulled are lost. This is an accepted limitation of the in-memory server.

P10.2 A client that detects a new epoch (in metadata or via `SERVER_EPOCH_CHANGED`) MUST stop syncing, keep all local data, and MUST NOT reuse its old cursor.

P10.3 Recovery: on an explicit reset action (user gesture or `reset_session` runner command), the client adopts the new epoch and sets its cursor to 0 in one transaction. All local events are kept. Outbox entries are resubmitted with their original envelopes. Already-accepted events are not resent; a recipient who already holds a resubmitted event from the old session sees no duplicate (P7.5).

## 11. Guarantees

Within one server session, while a client is running sync and can reach the server:
- Every outboxed event is eventually accepted or marked failed. None is silently lost, including across client restarts.
- Each event key is accepted at most once, however often it is retried.
- Each client stores each event at most once, however often a page is repeated.
- Every client sees its mailbox in the same `seq` order.

Not guaranteed: delivery latency, delivery while a client is suspended, read or delivered receipts, survival of server restarts, or correct behavior when one username is used on several devices at once.

## 12. Assignment scenario trace

Expected protocol state for the assignment's scenario, starting from a fresh server session. `test.md` owns the executable version; this table defines what correct looks like at the protocol level. Event texts are the assignment's where given.

| Step | Action | Server mailbox state | Client state after |
|---|---|---|---|
| 1 | Alice submits e1 to Bob ("Hi Bob, I have something important to tell you"); Bob pulls | bob: e1 (seq 1) | Bob holds e1; Bob cursor 1 |
| 2 | Bob submits e2 to Alice ("What is it?"); Alice pulls | alice: e2 (seq 2) | Alice holds e2; Alice cursor 2 |
| 3 | Alice offline; creates e3 to Bob | unchanged | e3 in Alice's outbox |
| 4 | Bob offline; creates e4 to Alice | unchanged | e4 in Bob's outbox |
| 5 | Alice reconnects: pulls (nothing new), submits e3 | bob: e1, e3 (seq 3) | e3 accepted; Alice outbox empty |
| 6 | Alice offline | unchanged | unchanged |
| 7 | Bob reconnects: pulls, then submits e4 | alice: e2, e4 (seq 4) | Bob holds e3, cursor 3; e4 accepted; Bob outbox empty |
| 8 | Alice reconnects and pulls (verification only) | unchanged | Alice holds e4; Alice cursor 4 |

The assignment's wording maps to protocol terms as follows. "Her queued message reaches the server" means accepted (P6.1). "Delivers his own queued message" in step 7 means accepted by the server; Alice has **not** received e4 at step 7, because she is offline. Step 8 is not in the assignment; it proves eventual receipt.

The scenario MUST pass with Alice on either client language and Bob on the other.