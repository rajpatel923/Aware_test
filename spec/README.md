# Shared scenarios

Test inputs and expected outcomes used by both clients, the server tests, and the cross-client runner in `tests/`. Expected results here are the oracle: never edit them to make failing code pass. Change them only together with `spec/behavior.md`.

## Files

- `identity.json`: username normalization cases (behavior.md section 2).
- `text.json`: text validation cases (behavior.md section 3).
- `alice_bob.json`: the required interoperability scenario (behavior.md section 14).
- `lost_ack.json`: a message accepted by the server whose response is lost (behavior.md 5.6, 6.1).
- `repeat_inbox.json`: an inbox response is lost; client must refetch without creating duplicates (behavior.md 7.3).
- `client_restart.json`: a queued message survives a client restart (behavior.md 4.1–4.4).
- `server_restart.json`: server restarts mid-session; clients detect epoch change, call reset_session, and resume (behavior.md 10.1–10.5, 11.1–11.7).
- `paging.json`: inbox spans multiple pages; all messages must be fetched in order without gaps or duplicates (behavior.md 7.1–7.4). Requires `--page-size 2`.

## Fixture notation

- `{"repeat": "a", "count": 4096}` means the string `a` repeated 4096 times.
- A `raw_json` value is sent as literal request-body JSON, for inputs that most languages cannot hold as a string (such as a lone surrogate).
- `$name` binds a value from an earlier result (`"bind": "m1"`) and refers to it later. IDs, sequences, epochs, and timestamps are never compared literally.
- `"note"` fields on any step or assertion are human-readable comments; harnesses must ignore them.
- `"runner_options"` on the fixture root sets per-run configuration for both runners. Supported keys: `page_size` (integer, overrides the default inbox page limit; runners accept `--page-size N`).

## Headless runner contract

Both runners read one JSON object per line on stdin and write one per line on stdout. Logs go to stderr only.

Request: `{"id": "1", "cmd": "send", "args": {"recipient": "bob", "text": "hi"}}`
Success: `{"id": "1", "ok": true, "result": {...}}`
Failure: `{"id": "1", "ok": false, "error": {"code": "...", "message": "..."}}`

| Command | Args | Result |
|---|---|---|
| `identify` | `name` | `username` (canonical) |
| `send` | `recipient`, `text` | `client_message_id`, `status` (`queued`) |
| `offline` | `enabled` (bool) | `offline` |
| `sync_once` | none | `outcome` (`ok`, `backoff`, `paused`, `server_reset`), `accepted`, `received`, `pending` |
| `snapshot` | `peer` (optional) | `username`, `server_epoch`, `cursor`, `sync_state`, `pending_count`, `messages` |
| `fault` | `drop_next_response` (`submit` or `inbox`) | `armed` |
| `reset_session` | none | `server_epoch`, `cursor` |
| `shutdown` | none | `{}` |

Each entry in `messages`: `client_message_id`, `sender`, `recipient`, `text`, `status` (`queued`, `accepted`, `failed`), `sequence` (null until accepted), `error_code` (null unless failed).

`fault` makes the transport discard the next matching response after the server has processed the request, then report a timeout. It is a test control in the transport wrapper, never in messaging logic.

Runners start with: base URL, data directory, and mode (`manual` or `automatic`) as command-line options. Exact flags are defined per platform once implemented.

## Harness directives

Some steps are harness directives, not runner commands. They have no `"id"` and are never sent on stdin.

| Step object | Meaning |
|---|---|
| `{"cmd": "restart", "client": "alice"}` | Shut down the named runner, then start a new instance with the same data directory and base URL. Bindings (`$m1`, etc.) are retained by the harness. |
| `{"cmd": "server_restart"}` | Stop the server process and start a fresh one. The new server has a new epoch and empty state. |

## Expectation notation (scenario files)

- `"expect": {"ok": true}` / `{"ok": false, "error_code": "..."}`: the command's outcome.
- `"expect": {"result": {...}}`: listed fields must match; others are ignored.
- `"expect": {"contains": [{...}]}` on `snapshot`: each listed message must appear exactly once with the listed fields.
- `"expect": {"absent": ["$m4"]}` on `snapshot`: those IDs must not appear.
