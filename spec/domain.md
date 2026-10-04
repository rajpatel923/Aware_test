# Domain Model

Status: draft, protocol version 1.

This file defines the entities, value rules, and states shared by the server and both clients. Field names here are the canonical names; on the wire they appear exactly as written (`api.md`). Platform code may use idiomatic casing (`eventId` in Swift and Kotlin) but MUST map to these names one-to-one. Protocol rules (`P…`) are in `protocol.md`; outbox and sync behavior in `offline-behavior.md`; display in `ui.md`.

## 1. Username

A username is the address of a mailbox. It is not an account: there is no registration, password, or uniqueness check. Any valid username can receive events before its owner has ever run a client.

D1.1 **Canonicalization**, applied in this exact order:
1. Remove leading and trailing ASCII space, tab, CR, and LF. No other characters are trimmed.
2. Convert ASCII `A`–`Z` to `a`–`z`. No other characters change case. Lowercasing MUST NOT depend on device locale.
3. Validate: the result MUST be 1–32 characters, each matching `[a-z0-9_]`.

D1.2 Inputs that canonicalize to the same value are the same user. Only canonical usernames are stored or sent on the wire.

D1.3 Examples: `"  Alice\n"` → `alice`; `"BOB_99"` → `bob_99`. Invalid: `""`, `"   "`, `"al ice"`, `"al-ice"`, `"Ālice"`, `"İstanbul"`, a leading non-breaking space, and anything over 32 characters. Full cases are in `test.md`.

## 2. Identity (client only)

The username this client acts as.

- `username`: canonical username.

D2.1 Exactly one identity per client data directory, saved durably before any network activity. Changing identity is out of scope for v1.

## 3. Event

The unit exchanged between clients through the server. Envelope rules are in `protocol.md` section 2.

| Field | Type | Set by | Notes |
|---|---|---|---|
| `event_id` | UUID string, lowercase, hyphenated | client | Generated once at creation; never changes |
| `type` | string | client | Registered event type (`protocol.md` P3.1) |
| `sender` | username | client | Always the client's own identity |
| `recipient` | username | client | Any valid username, including the sender |
| `body` | object | client | Schema defined by `type` (section 4) |
| `seq` | positive integer, or null | server | Null until accepted |
| `accepted_at` | UTC timestamp, ms precision, or null | server | Null until accepted; display only |

D3.1 The event key is `(sender, event_id)`.

D3.2 `event_id`, `type`, `sender`, `recipient`, and `body` are immutable once created.

D3.3 There is no client-side timestamp in the event. Device clocks are not trusted for anything.

## 4. Event bodies

### 4.1 `message.text`

- `text`: string.

D4.1 `text` MUST be valid Unicode and 1–4096 bytes when encoded as UTF-8. Length is always measured in UTF-8 bytes, never characters or UTF-16 units.

D4.2 `text` is stored, sent, and shown exactly as entered: no trimming, no Unicode normalization, no character replacement. Whitespace-only text is valid.

D4.3 Examples: `"hi"` is 2 bytes; `"é"` (U+00E9) is 2 bytes; `"e"` + combining accent U+0301 is 3 bytes and MUST NOT be converted to U+00E9; `"👋"` is 4 bytes. 4096 × `a` is valid; 4097 is not. 1024 × `👋` (4096 bytes) is valid; 1025 is not. Empty text and lone surrogates are invalid.

New body types are added by a new subsection here plus the steps in `protocol.md` P3.8.

## 5. Local event (client only)

An event as stored on a client: the full envelope from section 3, plus:

| Field | Type | Notes |
|---|---|---|
| `direction` | `outgoing` or `incoming` | `outgoing` when `sender` is this client's identity |
| `status` | see section 6 | Persisted |
| `local_order` | integer | Creation order for outgoing events; local only, never sent |
| `failure_code` | error code or null | Set only when `status` is `failed` |
| `epoch` | string or null | Server epoch in which `seq` was assigned |

D5.1 `local_order` is assigned when an outgoing event is created, increases by one per event, and is never reused. It only orders this client's own unaccepted events (`protocol.md` P8.2).

D5.2 A self-addressed event is stored once, as `outgoing`.

D5.3 Incoming events of an unknown type are stored like any other (`protocol.md` P3.5).

## 6. Status

D6.1 Persisted statuses:

- **Outgoing:** `queued` (in the outbox, not known to be accepted), `accepted` (the server holds it, with `seq`), `failed` (permanently rejected; see `failure_code`).
- **Incoming:** `received` (committed from the client's mailbox).

D6.2 Allowed transitions: `queued` → `accepted`; `queued` → `failed`. All others are invalid. `accepted`, `failed`, and `received` are final.

D6.3 `accepted` means the server stored the event. It does not mean the recipient has received or read it. There is no delivered or read status in v1.

D6.4 **Sending** is a display state only: shown while a `queued` event's request is in flight. It is never persisted, so a crash mid-request leaves the event `queued` and safely retryable.

## 7. Outbox entry (client only)

One per `queued` outgoing event.

- `event_id`: references the local event.
- `attempts`: integer, number of submissions tried.
- `last_error`: error code or null.

D7.1 An outbox entry exists if and only if its event is `queued`. Creating the event and its entry, and later removing the entry and changing the status, each happen in one transaction (`offline-behavior.md`).

## 8. Sync state (client only)

- `epoch`: the server epoch this client is synced with, or null before first contact.
- `cursor`: highest `seq` committed from this client's mailbox in `epoch`; starts at 0.

D8.1 `cursor` is meaningful only together with `epoch` and MUST NOT be reused with a different epoch (`protocol.md` P10.2).

## 9. Conversation (client only, derived)

A conversation is the set of local events between this client's identity and one peer: events where the peer is the other party. It is computed from local events, never stored separately, and does not exist on the server.

## 10. Server entities

- **Accepted event:** a full envelope with `seq` and `accepted_at`, immutable.
- **Mailbox:** per recipient username, the accepted events addressed to it, in `seq` order.
- **Event key index:** maps each `(sender, event_id)` to its accepted event, for idempotency (`protocol.md` P6.1).
- **Session:** the server's `epoch` and next `seq`.

The server stores no users, identities, outboxes, statuses, or cursors. All of these are client concepts.

## 11. Invariants

- A client never holds two local events with the same event key.
- An outgoing event has `seq` if and only if its status is `accepted`.
- Every incoming event has `seq`, `accepted_at`, and `epoch`.
- `cursor` never exceeds the highest `seq` the client has committed in `epoch`.
- No ordering, deduplication, or validity decision ever uses a device clock.

