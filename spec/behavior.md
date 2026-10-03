# Messaging Behavior Specification

Version: 1.0-draft. Path: `spec/behavior.md`.

This is the authoritative definition of what the server and both clients must do. `spec/protocol.openapi.yaml` defines wire formats; `spec/scenarios/` holds shared test cases. If code, tests, or other documents disagree with this file, this file wins until it is deliberately changed. MUST, MUST NOT, and MAY are used in their normal requirement sense.

Items marked **[DECISION NEEDED]** are proposed defaults that must be confirmed before implementation depends on them.

## 1. Terms

- **Server session:** the lifetime of one server process. Identified by a **server epoch**, an opaque string generated at startup.
- **Canonical username:** a username after normalization (section 2). It is the mailbox identifier.
- **Message key:** the pair `(sender, client_message_id)`. Unique within a server session.
- **Sequence:** a positive integer the server assigns when it accepts a message.
- **Cursor:** the highest sequence a client has committed from its own inbox in the current epoch. Starts at 0.
- **Outbox:** the client's durable list of messages not yet accepted by the server.
- **Accepted:** the server has stored the message. It does not mean the recipient has received or read it.

## 2. Identity

2.1 Normalization MUST be applied in this order: remove leading and trailing ASCII space (U+0020), tab (U+0009), CR (U+000D), and LF (U+000A); convert ASCII `A`–`Z` to `a`–`z`; then validate.

2.2 A canonical username MUST be 1–32 characters, each matching `[a-z0-9_]`. Anything else is invalid. No other Unicode trimming, case folding, or normalization is allowed, and lowercasing MUST NOT depend on the device locale.

2.3 Usernames that normalize to the same value are the same user.

2.4 A client MUST save its username durably before any network activity. Each client data directory holds exactly one identity; changing it is out of scope for v1.

2.5 No registration exists. Any valid username can receive messages before its user has ever run a client.

2.6 Usernames identify mailboxes but prove nothing about who is using them. There is no authentication.

| Input | Result |
|---|---|
| `"  Alice\n"` | `alice` |
| `"BOB_99"` | `bob_99` |
| `""`, `"   "` | invalid (empty after trimming) |
| `"al ice"` | invalid (inner space) |
| `"Ālice"` | invalid (non-ASCII letter) |
| `"\u00A0alice"` | invalid (non-breaking space is not trimmed and not allowed) |
| 33 × `a` | invalid (too long) |

## 3. Messages

3.1 A message has a sender, a recipient, text, and a `client_message_id`. All four are immutable once the message is created.

3.2 Text MUST be a valid Unicode string whose UTF-8 encoding is 1–4096 bytes. Length MUST be measured in UTF-8 bytes on every platform, never in characters or UTF-16 units.

3.3 Text MUST be stored, sent, and displayed exactly as entered: no trimming, no Unicode normalization, no replacement of characters. Whitespace-only text is valid.

3.4 `client_message_id` MUST be a lowercase, hyphenated UUID (version 4 when generated). The client creates it once, before the message is first stored, and MUST NOT change it on retry.

3.5 A user MAY send a message to themselves.

| Text | UTF-8 bytes | Result |
|---|---|---|
| `"hi"` | 2 | valid |
| `""` | 0 | invalid |
| `" "` | 1 | valid |
| `"é"` (U+00E9) | 2 | valid; stays U+00E9 |
| `"e\u0301"` (e + combining accent) | 3 | valid; MUST NOT be converted to U+00E9 |
| `"👋"` | 4 | valid |
| 4096 × `a` | 4096 | valid |
| 4097 × `a` | 4097 | invalid |
| 1024 × `👋` | 4096 | valid |
| 1025 × `👋` | 4100 | invalid |
| a lone surrogate (e.g. JSON `"\ud800"`) | n/a | invalid |

## 4. Client message states

4.1 Every locally stored message has exactly one persisted status:
- **queued:** created locally and in the outbox; not known to be accepted.
- **accepted:** the server has accepted it (an acknowledgement or inbox record confirmed it).
- **failed:** permanently rejected; not in the outbox and never retried automatically.

4.2 Received messages are stored as `accepted`.

4.3 Clients MAY display **Sending** while a queued message's request is in flight. It is not a persisted status.

4.4 Clients MUST NOT display "delivered" or "read". v1 has no receipt information.

4.5 Allowed transitions: queued → accepted; queued → failed; failed is final; accepted is final.

## 5. Sending

5.1 **Enqueue.** Creating a message MUST, in one local transaction: assign the next local enqueue order, store the message as `queued`, and add its outbox entry. Only after this commits may the client report the message as queued or clear the composer. Enqueue MUST work with no network.

5.2 If enqueue fails, nothing is stored and the user's draft MUST be kept.

5.3 **Submission.** The client submits outbox entries in enqueue order, at most one request in flight at a time. If the oldest entry fails with a retryable error, later entries MUST wait, preserving the user's sending order.

5.4 **Retry.** A retry MUST resend the identical `client_message_id`, sender, recipient, and text.

5.5 **Acceptance.** On a valid acknowledgement, the client MUST, in one transaction: check that the acknowledgement matches the stored message key and content, store the sequence, acceptance time, and epoch, set status `accepted`, and remove the outbox entry. A mismatched acknowledgement is a protocol error (section 9).

5.6 **Ambiguity.** A timeout, disconnect, or cancellation does not mean the server rejected the message. The outbox entry MUST be kept and retried.

5.7 **Permanent rejection.** If the server rejects a specific message as invalid or as a key conflict, the client MUST, in one transaction, mark it `failed` with the error code and remove its outbox entry. Later messages then proceed.

## 6. Server acceptance

6.1 For a valid submission with the current epoch, the server MUST perform the following as one indivisible operation:
- If the message key is new: assign the next sequence, store the message with its acceptance time, add it to the recipient's mailbox, and return it.
- If the key exists with identical recipient and text: return the original stored result unchanged, with the same sequence and acceptance time, and add nothing.
- If the key exists with a different recipient or text: reject with `MESSAGE_ID_CONFLICT` and change nothing.

6.2 First acceptance and identical retry return the same success response.

6.3 Sequences are positive, start at 1 in each session, and strictly increase across all accepted messages, regardless of recipient. Gaps within one user's inbox are normal.

6.4 Acceptance time is UTC with millisecond precision. It is for display only and MUST NOT be used for ordering or cursors.

6.5 Invalid requests MUST NOT change server state or consume a sequence.

6.6 The server MUST keep every accepted message and message key for the whole session. Reading an inbox MUST NOT delete or alter anything.

## 7. Receiving

7.1 A client fetches its own inbox with its cursor as `after`. The server returns that recipient's messages with sequence greater than `after`, in ascending sequence order, up to `limit` (default and maximum 100). `has_more` is true when further messages exist beyond the page. `next_cursor` is the last returned sequence, or `after` if the page is empty.

7.2 Before storing a page, the client MUST check that: the epoch matches its saved epoch; every message is addressed to its own canonical username; all required fields are present and valid; sequences strictly increase and exceed the requested cursor; `next_cursor` equals the last sequence (or the requested cursor if empty); and an empty page does not claim `has_more`. Any failure is a protocol error and nothing from the page is stored.

7.3 A valid page MUST be stored in one transaction together with the new cursor and epoch. If any part fails, the whole page and cursor are rolled back.

7.4 A message the client already has (same message key, identical content) MUST NOT create a second visible message. The client MAY fill in missing acceptance details. If a self-sent message still `queued` locally arrives in the inbox, the same transaction MUST mark it `accepted` and remove its outbox entry.

7.5 A received message with a known key but different content is a protocol error. The stored message MUST NOT be overwritten.

7.6 The cursor MUST only advance through 7.3. It MUST NOT be advanced from a send acknowledgement, a timestamp, or any other source.

## 8. Display order

8.1 Within a conversation, accepted messages are shown in ascending sequence order, then queued and failed messages in ascending local enqueue order.

8.2 A message written offline may therefore appear after one the server accepted earlier. This is intended; the server's order is the shared truth.

8.3 Messages from a previous epoch (section 10) are shown before current-epoch messages, in their original order.

## 9. Errors and client reactions

| Condition | Server response | Client MUST |
|---|---|---|
| Invalid username, text, ID, field, type, header, or unknown request field | 422 `INVALID_REQUEST` | Mark that message `failed`; never silently drop it |
| Same key, different recipient or text | 409 `MESSAGE_ID_CONFLICT` | Mark that message `failed`; no retry |
| Epoch header differs from the server's | 409 `SERVER_EPOCH_CHANGED` | Enter Server reset (section 10) |
| Cursor below 0 or above the session's highest sequence | 422 `INVALID_CURSOR` | Pause sync and report a protocol error; never reset the cursor silently |
| Timeout, disconnect, 5xx, 429 | none or error | Keep the outbox; retry with backoff (honor a valid `Retry-After` on 429) |
| Malformed success, unexpected status, mismatched acknowledgement, invalid page | n/a | Pause sync and report a protocol error; treat nothing as accepted |
| Local transaction fails | n/a | Keep the last committed state; pause and report a storage error |
| Request cancelled by the app | n/a | Keep pending work |

All server errors use one envelope: `code`, `message`, and `server_epoch` where available. Framework validation errors MUST use the same envelope.

Protocol and storage errors pause automatic sync until the user (or runner) explicitly resumes.

## 10. Server sessions and restarts

10.1 A server restart starts a new session: a new epoch, sequences from 1, and no messages or keys. Messages accepted by the old session but not yet received are lost. This is an accepted limitation.

10.2 A client with no saved epoch adopts the epoch from `GET /v1/meta`. Every later inbox read and submission MUST send the saved epoch.

10.3 If the epoch differs from the saved one (via meta or `SERVER_EPOCH_CHANGED`), the client MUST stop automatic sync, keep all local data, and show that the server restarted. It MUST NOT reuse its old cursor with the new server.

10.4 **Leaving the reset state.** A client operation `resetSession()` (headless command `reset_session`) that, in one transaction, adopts the new epoch, sets the cursor to 0, and keeps all messages. Queued messages stay queued and are resubmitted with their original IDs; already-accepted messages are not resent. The UI triggers it from the restart banner. No server endpoint is involved.

10.5 Consequence of 10.4: a recipient who received a message in the old session may receive the same message key again in the new one. Rule 7.4 prevents a visible duplicate. No guarantee is made for messages lost in 10.1.

## 11. Sync behavior

11.1 Each client runs at most one sync cycle at a time. Requests to sync while one is running MUST wake or join it, never start a second.

11.2 A cycle: confirm or adopt the epoch (10.2–10.3); fetch and store one inbox page (section 7); then submit up to 10 outbox entries in order (section 5). If more inbox pages or outbox entries remain, start another cycle promptly; otherwise wait for the poll interval.

11.3 Sync runs only while the client is active: the app is in the foreground, or a headless runner is in automatic mode. Manual mode runs exactly one cycle per `sync_once` command.

11.4 No local transaction may stay open during a network request. Enqueue MUST remain possible while sync is running.

11.5 Connectivity notifications from the OS MAY trigger a sync but MUST NOT be required. The server may be reachable without internet access.

11.6 When an app goes to the background, sync pauses; all committed data and the outbox are kept. Nothing is promised while suspended.

11.7 Results from a cancelled or superseded cycle MUST NOT overwrite newer state.

## 12. Timing defaults

| Setting | Value |
|---|---|
| Poll interval (active and caught up) | 1 s after a cycle completes |
| Request timeout | 10 s per request |
| Retry backoff | 1, 2, 4, 8, 16, then 30 s; reset after a successful cycle |
| Inbox page size | default and maximum 100 |
| Submissions per cycle | up to 10 |

These are design choices, not measured requirements. Tests may shorten them through injected clocks.

## 13. Guarantees

Within one server session, while a client is active and the server is reachable:
- Every queued message is eventually accepted or marked `failed`; none is silently lost, including across client restarts.
- Each message is accepted at most once, regardless of retries.
- Each recipient stores each message at most once, regardless of repeated pages.
- Recipients see messages in server sequence order.

Not guaranteed: delivery timing, delivery while a client is suspended, read status, survival of server restarts, or correct behavior for one username used on several devices.

## 14. Required scenario

Using one Swift client and one Kotlin client against one server session, then again with roles swapped:
1. Alice and Bob exchange messages online; each sees the other's exact text.
2. Both go offline; each enqueues one message, which is stored as `queued`.
3. Alice comes online; her message becomes `accepted`.
4. Alice goes offline.
5. Bob comes online; he receives Alice's message exactly once, and his message becomes `accepted`.
6. Alice comes online and receives Bob's message.

At step 5, Alice has not received Bob's message; only step 6 shows receipt. Exact message texts and expected states live in `spec/scenarios/`.