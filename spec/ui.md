# UI

Status: draft, protocol version 1.

This file defines the two screens every client must provide and how each piece of state is displayed. It adds no behavior; every rule that affects what the user sees is in `domain.md`, `protocol.md`, and `offline-behavior.md`. Platform implementation choices are in `platform/ios.md` and `platform/android.md`. Rules carry IDs (`U…`).

## 1. Screens

Two screens are required. No other screens are required.

### 1.1 Identify screen

Shown when the client has no saved identity (`domain.md` D2.1).

| Element | Description |
|---|---|
| Name field | Text input for the username |
| Submit action | Canonicalize and save the name; navigate to the conversation screen on success |
| Validation error | Shown inline when the input does not survive canonicalization (D1.1); the field is preserved |

U1.1 The client MUST apply canonicalization (`domain.md` D1.1) before saving. The raw input is not stored.

U1.2 Identification requires no network. The screen MUST NOT show a loading indicator or wait for a server response.

U1.3 Once identified, the client MUST NOT show this screen again in the same installation. Changing identity is out of scope for v1.

### 1.2 Conversation screen

Shown once identity is saved. It has four areas: the peer selector, the message list, the composer, and the sync banner.

**Peer selector:** the recipient the user is currently addressing. In v1, a simple text field is sufficient. A list of previously contacted peers may be derived from cached events; it does not require a server directory.

**Message list:** all local events between this client's identity and the selected peer, in display order (section 3). Each row shows the sender, text (for `message.text` events), status badge, and acceptance time when available.

**Composer:** a text field and a send action. The send action is disabled when the text is empty or the recipient field is blank.

**Sync banner:** a one-line indicator of the current sync state (section 4). Hidden when the state is `idle`.

## 2. Send action

U2.1 On Send: capture the draft text and recipient; await `enqueue`; clear the composer **only after the local transaction commits** (`offline-behavior.md` O2.3). If the user edited the draft while the enqueue was in progress, do not overwrite the newer text compare the captured draft or use a submission token.

U2.2 If enqueue fails (`storage_error`), keep the draft intact and show the error.

U2.3 Do not wait for HTTP acceptance to clear the composer. A successfully enqueued event is local success.

## 3. Display order

U3.1 Show accepted incoming and outgoing events (status `received` or `accepted`) in ascending `seq` order within the current epoch (`protocol.md` P8.1, P8.2).

U3.2 Show pending and failed outgoing events (status `queued` or `failed`) in a separate trailing group after all accepted events, ordered by `local_order` ascending.

U3.3 A `queued` event may move from the trailing group into the accepted sequence when acknowledged. Do not imply the server sequence captures composition time.

U3.4 Events from a previous server epoch are shown with a visual separator or epoch label so the user can see that a server restart occurred.

## 4. Sync status display

Show the sync banner whenever the state is not `idle`:

| State | Suggested text                        | Dismissible                    |
|---|---------------------------------------|--------------------------------|
| `syncing` | "Syncing…"                            | No                             |
| `offline` | "Offline will retry"                  | No                             |
| `paused` | *(hidden; normal inactive state)*     | -                              |
| `server_reset` | "Server restarted. Tap to reconnect." | Requires explicit reset action |
| `incompatible` | "Server version not supported."       | No                             |
| `protocol_error` | "Sync error - contact support."       | No                             |
| `storage_error` | "Storage error - restart the app."    | No                             |

U4.1 The sync banner always reflects the current derived state (`offline-behavior.md` O10.7). After relaunch, banners for `incompatible` and `protocol_error` are not shown until the first cycle re-detects the problem; `server_reset` reappears after the first session check; `storage_error` is shown immediately if storage fails to open.

U4.2 The pending count (number of events in the outbox) MAY be shown alongside the sync state, e.g. "Syncing… (2 pending)".

## 5. Event status badges

Each event row shows a status badge:

| Status | Badge                                                   | Meaning |
|---|---------------------------------------------------------|---|
| `queued` | Clock or hourglass                                      | Saved locally, not yet submitted |
| `sending` | Spinner (transient, never persisted - `domain.md` D6.4) | Submission currently in flight |
| `accepted` | Single check                                            | Server confirmed receipt |
| `failed` | Exclamation or ✗                                        | Permanently rejected; `failure_code` available |
| `received` | No badge, or distinct row style                         | Incoming event from another user |

U5.1 `accepted` means the server stored the event, not that the recipient has read it. Do not show a double check or "delivered" label without a receipt contract (`domain.md` D6.3, out of scope for v1).

U5.2 For a `failed` event, show `failure_code` in a tooltip or secondary label where feasible.

## 6. Unknown event types

U6.1 An event with an unknown type (`protocol.md` P3.5) MUST be shown as a neutral placeholder, for example: `[Unsupported message type: reaction.add]`. It MUST NOT be hidden, because hiding it would misrepresent the conversation.

U6.2 Unknown types MUST NOT cause the UI to crash, stall, or show an error banner. They are a normal part of the extension mechanism.

## 7. Constraints

U7.1 Views MUST NOT call storage, HTTP, or the sync engine directly. All calls go through the messaging facade.

U7.2 Views MUST NOT maintain a second authoritative array of messages. The single source of truth is the core snapshot backed by storage.

U7.3 View-scoped subscriptions MUST be cancelled when the view disappears. Cancellation MUST NOT delete queued messages or reset the cursor.

U7.4 No view MUST sleep, poll, or use a hard-coded timeout. Responsiveness comes from observing state, not timing.
