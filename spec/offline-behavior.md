# Offline Behavior

Status: draft, protocol version 1.

This file defines how a client stays usable without the server and how it catches up: creating events locally, the outbox, the sync cycle, retries, connectivity, app lifecycle, and recovery. Entities and statuses are in `domain.md`; wire rules in `protocol.md`; display of sync state in `ui.md`; test controls and scenarios in `test.md`. Rules carry IDs (`O…`).

## 1. Principle

O1.1 The client is local-first. Every user action (identify, send, read history) completes against local storage, with or without a server. The network is used only to sync: submit outbox entries and pull the mailbox.

O1.2 "Offline" is not a flag the client reads from the OS. A client is effectively offline whenever requests fail to complete, for any reason: no network, server down, unreachable host, or the test network gate (`test.md`). All of these are handled identically.

O1.3 Being offline MUST NOT block, slow, or lose any local action. Nothing visible changes except sync status and outgoing events staying `queued`.

## 2. Creating an outgoing event

O2.1 Before creating an event, the client validates it locally: recipient per `domain.md` D1, body per its type (D4 for `message.text`). Invalid input is rejected immediately; nothing is stored.

O2.2 **Type availability.** `message.text` is a base type and is always allowed, including before the client has ever contacted a server. Any other type is allowed only if the last server metadata the client saved advertised it (`protocol.md` P3.4).

O2.3 **Enqueue transaction.** In one local transaction the client MUST: generate `event_id`; assign the next `local_order`; store the local event with direction `outgoing` and status `queued`; create its outbox entry with `attempts` 0. Only after this commits may the client report success or clear the composer.

O2.4 If the transaction fails, nothing is stored, the user's draft is kept, and the error is shown.

O2.5 Enqueue MUST NOT wait on the network, on a running sync, or on a lock held across a network call. A user can enqueue while a submission is in flight.

O2.6 After a successful enqueue, the client requests a sync (O5.1). Whether that sync succeeds has no effect on the enqueue result.

## 3. Outbox

O3.1 The outbox holds exactly the outgoing events with status `queued` (`domain.md` D7.1). It survives app restarts, crashes, and process death.

O3.2 Entries are submitted strictly in `local_order` (`protocol.md` P5.2, P5.7). The oldest entry is the head.

O3.3 Entries are never removed except by the acceptance or permanent-rejection transactions in section 4. There is no expiry, size-based eviction, or user-visible "discard" in v1.

## 4. Submission outcomes

Each submission of the head entry ends in exactly one of these outcomes:

O4.1 **Accepted.** The response matches the stored event (`protocol.md` P5.5). In one transaction: set `seq`, `accepted_at`, and `epoch`; set status `accepted`; delete the outbox entry. Continue with the next entry.

O4.2 **Permanently rejected** (`INVALID_REQUEST`, `UNSUPPORTED_TYPE`, `EVENT_ID_CONFLICT`). In one transaction: set status `failed` and `failure_code`; delete the outbox entry. Continue with the next entry.

O4.3 **Outcome unknown** (timeout, connection failure, 5xx, 429, cancellation). Increment `attempts`, record `last_error`, keep the entry, and stop submitting for this cycle. The next attempt resends the identical envelope (`protocol.md` P5.3).

O4.4 **Epoch changed.** Stop the cycle and enter server-reset handling (section 9). Keep the entry.

O4.5 **Protocol error** (malformed or mismatched response). Keep the entry, stop syncing, and enter the protocol-error state (section 7).

O4.6 A crash at any point leaves the entry in the outbox, because removal only happens inside the transactions in O4.1 and O4.2. Retrying after a crash is always safe.

## 5. Sync cycle

O5.1 **Triggers.** A sync is requested when: the client becomes active; an event is enqueued; the poll interval elapses while caught up; a backoff delay elapses; the OS reports a connectivity change; or a test issues a manual sync. Triggers only request a sync; they never start a second one (O6.1).

O5.2 **One cycle**, in this order:
1. **Session check.** If no metadata has been fetched since the client became active, or after any error, fetch it. Apply `protocol.md` P4.2 (version) and P10.2 (epoch). Save the advertised event types.
2. **Pull.** Fetch one page after the saved cursor and commit it with the cursor in one transaction (`protocol.md` P7.3–P7.6).
3. **Submit.** Submit up to 10 outbox entries, one at a time, in order, applying section 4.

O5.3 Pull happens before submit. In the assignment's step 7, this is why Bob first receives Alice's message and then delivers his own.

O5.4 If the page reported more events, or outbox entries remain and the last outcome was success, the next cycle starts immediately. Otherwise the client waits for the poll interval.

O5.5 If any step fails with an outcome-unknown error, the cycle ends and the client enters backoff (section 8). Committed work from earlier steps stays committed.

## 6. Concurrency

O6.1 A client runs at most one sync cycle at a time. A trigger during a cycle marks that another cycle is wanted and returns; it never starts a parallel one.

O6.2 No local transaction stays open across a network request.

O6.3 Each cycle belongs to an activation generation. If the client is deactivated, closed, or reset while a cycle is in flight, results from that cycle MUST NOT be committed.

O6.4 Cancelling a cycle never discards committed data or outbox entries.

## 7. Sync states

The client exposes exactly one sync state at a time, for display (`ui.md`) and tests:

- `idle`: active and caught up; waiting for the poll interval.
- `syncing`: a cycle is running.
- `offline`: the last cycle ended with outcome unknown; waiting for backoff. Outbox entries stay `queued`.
- `paused`: the client is inactive (backgrounded, or manual test mode between commands).
- `server_reset`: a new server epoch was detected (section 9).
- `incompatible`: the server's protocol version differs (`protocol.md` P4.2).
- `protocol_error`: a response or page failed validation.
- `storage_error`: a local transaction failed.

O7.1 `server_reset`, `incompatible`, `protocol_error`, and `storage_error` stop automatic sync. Only an explicit user or test action resumes it. Local reading and enqueueing still work in every state.

## 8. Timing

| Setting | Value |
|---|---|
| Poll interval when caught up | 1 s after a cycle ends |
| Request timeout | 10 s per request |
| Backoff after outcome-unknown | 1, 2, 4, 8, 16, then 30 s (cap) |
| Backoff reset | after any cycle that completes without error |
| `Retry-After` on 429 | honored if valid, otherwise normal backoff |
| Submissions per cycle | up to 10 |

O8.1 These values are defaults, not measured requirements. Tests MAY shorten them through an injected clock; behavior MUST otherwise be identical.

O8.2 A connectivity-change trigger ends the current backoff wait early. It MUST NOT be required: a local server can be reachable when the OS reports no internet, and vice versa.

## 9. Server restart

O9.1 On a new epoch (`protocol.md` P10.2), the client enters `server_reset`: it stops syncing, keeps all local events and outbox entries, and does not use its cursor.

O9.2 Recovery follows `protocol.md` P10.3. An explicit reset action (user gesture or `reset_session` runner command) adopts the new epoch and sets the cursor to 0 in one transaction. All local events are kept. Outbox entries are resubmitted with their original envelopes starting from the next sync cycle.

## 10. Lifecycle

O10.1 **Active** means the app is in the foreground, or a headless runner is in automatic mode. Sync runs only while active.

O10.2 **Becoming inactive** (background, screen lock) cancels the running cycle per O6.3 and stops timers. Nothing is deleted.

O10.3 **Becoming active** requests a sync immediately.

O10.4 **Restart** (app relaunch, crash, process death): on load, the client reads identity, local events, outbox, and sync state from storage and resumes exactly where the last commit left it. No in-memory state is required to recover.

O10.5 v1 makes no promise of syncing while the app is suspended: no background tasks and no push notifications.

## 11. Storage requirements

O11.1 All state in `domain.md` sections 2, 5, 7, and 8 is durable: stored in the app's persistent storage, never in cache or temporary directories.

O11.2 The transactions in O2.3, O4.1, O4.2, and `protocol.md` P7.4 MUST be atomic: after a crash, either all of their changes are present or none are.

O11.3 Schema changes use versioned migrations. A failed migration enters `storage_error` and MUST NOT delete or reset the database.

## 12. Assignment steps covered

- Steps 3–4 (go offline, queue a message): O1.2, O2.3, O3.1.
- Step 5 (reconnect, queued message reaches the server): O5.1, O5.2, O4.1.
- Step 6 (offline again): O1.3, O10.2 or O4.3.
- Step 7 (reconnect, receive, then deliver): O5.2, O5.3, O4.1.

The full expected state at each step is in `protocol.md` section 12.