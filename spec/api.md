# HTTP API

Status: draft, protocol version 1.

This file defines the wire format: endpoints, headers, JSON shapes, status codes, and validation order. Semantics (what acceptance, cursors, and epochs mean) are in `protocol.md`; field rules (usernames, text, statuses) in `domain.md`. This file is authoritative for anything that crosses the network. Rules carry IDs (`A…`).

## 1. General

A1.1 Transport is plain HTTP/1.1 on a local network. The base URL is configurable; the default is `http://127.0.0.1:8000`. How emulators and simulators reach it is in `platform/*.md`.

A1.2 Request and response bodies are JSON (RFC 8259), encoded as UTF-8, with `Content-Type: application/json`. Requests with another content type, invalid UTF-8, invalid JSON, or duplicate object keys are rejected with `INVALID_REQUEST`.

A1.3 Field names are snake_case and appear exactly as in `domain.md`. Platform code maps them to idiomatic names.

A1.4 Every response carries `Cache-Control: no-store`. Clients MUST NOT cache responses.

A1.5 Request bodies larger than 16 KiB are rejected with status 413 and code `INVALID_REQUEST`.

A1.6 **Strict requests, tolerant responses.** The server rejects unknown fields in requests (in the envelope and in bodies of known types). Clients ignore unknown fields in responses but require every field this file marks as present. This lets the server add response fields without breaking older clients.

## 2. Value formats

| Value | Format |
|---|---|
| Username | String matching `^[a-z0-9_]{1,32}$`, already canonical (`domain.md` D1). The server does not normalize; non-canonical input is `INVALID_REQUEST`. |
| `event_id` | Lowercase hyphenated UUID: `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$` |
| `type` | `^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$` (`protocol.md` P3.2) |
| `seq`, cursors | JSON integer, 1 to 2^53−1 for `seq`; 0 to 2^53−1 for cursors. The 2^53 cap keeps values exact in every JSON library. |
| `accepted_at` | UTC, exactly `YYYY-MM-DDTHH:MM:SS.sssZ` (e.g. `2026-10-03T14:05:09.123Z`) |
| Server epoch | Opaque string matching `^[A-Za-z0-9_-]{1,64}$` |
| `protocol_version` | JSON integer |

A2.1 Numbers in JSON MUST be integers where integers are required: `1.0`, `"1"`, and `true` are invalid.

## 3. Endpoints

| Method and path | Purpose | Epoch header |
|---|---|---|
| `GET /v1/meta` | Protocol version, epoch, supported event types | Not sent |
| `POST /v1/events` | Submit one event | Required |
| `GET /v1/mailboxes/{username}/events` | Pull one page of a mailbox | Required |

A3.1 Every request except `GET /v1/meta` MUST carry `X-Server-Epoch` with the client's saved epoch (`protocol.md` P4.4). Missing or malformed is `INVALID_REQUEST`.

A3.2 Unknown paths return 404 and unsupported methods 405, both with the error envelope and code `INVALID_REQUEST`.

### 3.1 `GET /v1/meta`

Response 200:

```json
{
  "protocol_version": 1,
  "server_epoch": "k3P9xQ2mVw",
  "event_types": ["message.text"]
}
```

All three fields are always present. `event_types` lists exactly the types the server accepts (`protocol.md` P4.1).

### 3.2 `POST /v1/events`

Request:

```json
{
  "event_id": "3f6c2a9e-8b1d-4c7a-9e2f-1a2b3c4d5e6f",
  "type": "message.text",
  "sender": "alice",
  "recipient": "bob",
  "body": { "text": "Hi Bob, I have something important to tell you" }
}
```

All five fields are required. `seq` and `accepted_at` MUST NOT be sent.

Response 200, for a first acceptance and for an identical retry alike (`protocol.md` P6.1–P6.2):

```json
{
  "event_id": "3f6c2a9e-8b1d-4c7a-9e2f-1a2b3c4d5e6f",
  "type": "message.text",
  "sender": "alice",
  "recipient": "bob",
  "body": { "text": "Hi Bob, I have something important to tell you" },
  "seq": 1,
  "accepted_at": "2026-10-03T14:05:09.123Z",
  "server_epoch": "k3P9xQ2mVw"
}
```

A3.3 The server checks a submission in this order and returns the first failure:
1. Epoch header present and well-formed, else 422 `INVALID_REQUEST`.
2. Body is valid JSON with exactly the five envelope fields in the right formats, else 422 `INVALID_REQUEST`.
3. Epoch matches, else 409 `SERVER_EPOCH_CHANGED`.
4. `type` is in `event_types`, else 422 `UNSUPPORTED_TYPE`.
5. `body` is valid for its type (`domain.md` section 4), else 422 `INVALID_REQUEST`.
6. Event key is new, or exists with an identical envelope, else 409 `EVENT_ID_CONFLICT`.

A3.4 No failure at any step changes server state (`protocol.md` P6.4).

### 3.3 `GET /v1/mailboxes/{username}/events`

Query parameters:
- `after`: cursor, integer ≥ 0. Optional; default 0.
- `limit`: integer 1–100. Optional; default 100.

Query values MUST be plain decimal digits with no sign, spaces, or leading zeros (except `0` itself), else `INVALID_REQUEST`.

Response 200:

```json
{
  "server_epoch": "k3P9xQ2mVw",
  "events": [
    {
      "event_id": "3f6c2a9e-8b1d-4c7a-9e2f-1a2b3c4d5e6f",
      "type": "message.text",
      "sender": "alice",
      "recipient": "bob",
      "body": { "text": "Hi Bob, I have something important to tell you" },
      "seq": 1,
      "accepted_at": "2026-10-03T14:05:09.123Z",
      "server_epoch": "k3P9xQ2mVw"
    }
  ],
  "next_cursor": 1,
  "has_more": false
}
```

A3.5 `events` contains only events whose `recipient` is `{username}`, with `seq > after`, in ascending `seq`, at most `limit` of them. `next_cursor` is the last returned `seq`, or `after` if `events` is empty. `has_more` is true only if more matching events exist. An empty page always has `has_more: false`.

A3.6 Checks, in order: epoch header well-formed; `{username}`, `after`, and `limit` well-formed (else 422 `INVALID_REQUEST`); epoch matches (else 409 `SERVER_EPOCH_CHANGED`); `after` does not exceed the highest `seq` in the session (else 422 `INVALID_CURSOR`).

A3.7 There is no authentication: any client can read any mailbox. This is an accepted limitation of the local demo (`protocol.md` section 11).

## 4. Errors

Every non-200 response uses one envelope:

```json
{
  "code": "SERVER_EPOCH_CHANGED",
  "message": "Server restarted; saved epoch is no longer valid.",
  "server_epoch": "Zt8Lq1nRx4"
}
```

`code` and `message` are always present; `server_epoch` is always present for responses from a running server. `message` is for humans and MUST NOT be parsed.

| Status | `code` | When |
|---|---|---|
| 409 | `EVENT_ID_CONFLICT` | Same event key, different content |
| 409 | `SERVER_EPOCH_CHANGED` | Saved epoch is not the current one |
| 413 | `INVALID_REQUEST` | Body over 16 KiB |
| 404, 405 | `INVALID_REQUEST` | Unknown path or method |
| 422 | `INVALID_REQUEST` | Malformed request, header, field, or body |
| 422 | `UNSUPPORTED_TYPE` | Type not in `event_types` |
| 422 | `INVALID_CURSOR` | `after` beyond the session's highest `seq` |
| 500 | `INTERNAL_ERROR` | Unexpected server failure; clients treat it as retryable |

A4.1 Framework-generated errors (for example a web framework's own validation responses) MUST be converted to this envelope. No other error shape is allowed.

A4.2 Client handling of each code is defined in `protocol.md` section 9 and `offline-behavior.md` section 4. Any status not in this table is treated as a protocol error.

## 5. Timeouts and retries

A5.1 Clients use a 10-second timeout per request (`offline-behavior.md` section 8).

A5.2 Retries are decided by the client's sync logic, never by an HTTP library's automatic retry. Automatic retries MUST be disabled, because they would hide outcomes from the outbox logic.

A5.3 A response that arrives but cannot be parsed, or fails A1.6 or section 2, is a protocol error, not a retryable failure.