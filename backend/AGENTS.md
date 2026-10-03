# backend/AGENTS.md

Rules for work under `backend/`. These refine root `AGENTS.md`; read both. Paths are relative to the repository root.

## Scope

A small Python/FastAPI server that both clients talk to: one process, one worker, in-memory state that lasts until the process exits. Task B01 in `.agent/task.md`. Nothing below exists yet; do not create files just because they are listed here.

Before writing behavior, read `spec/behavior.md`, `spec/protocol.openapi.yaml`, `spec/scenarios/`, and design sections 3–6. The spec wins over this file, the design, FastAPI defaults, and its generated OpenAPI. If the spec is missing or ambiguous, report it and continue only independent work.

## Commands

All commands run from `backend/`.

| Purpose | Command | Status |
|---|---|---|
| Create venv | `python -m venv .venv` | PASS |
| Install deps | `.venv/bin/pip install -r requirements.txt` | PASS |
| Run server (single worker, no reload) | `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1` | PASS |
| Run all tests | `.venv/bin/pytest tests/ -v` | PASS (27/27) |
| Readiness check | `curl -s http://127.0.0.1:8000/v1/meta` | PASS (returns version + epoch) |

## Ownership

Backend tasks own `backend/` only, including its tests and package config. Never edit `spec/`, `tests/`, root instructions, `.agent/task.md`, or client code; propose changes in the handoff instead. Never fix a server bug by weakening a shared expected result.

## Layout

One app, four layers, under `backend/app/`:
- `main.py`, `config.py`: build the app, epoch, store, service, and routes once; parse settings. No business rules.
- `api/routes.py`, `api/schemas.py`, `api/errors.py`: decode requests, validate wire shape, map results and errors to HTTP. Never touch store indexes.
- `domain.py`, `service.py`: identity and text rules, immutable message records, typed errors, use cases. No FastAPI types.
- `repository.py`, `memory_store.py`: the two atomic operations below, plus epoch, sequence counter, and indexes. No HTTP formatting.

Tests live in `backend/tests/`; cross-client tests stay in `tests/`. Use plain typed Python and constructor injection: no DI container, event bus, or generic CRUD layer. Put each rule in one place; never duplicate normalization across handlers. Do not create empty files to match this list.

## State and concurrency

Create one store per app instance at startup and share it across routes. No per-request stores and no module-level mutable singletons, so separate test apps never share state. The store holds the epoch, a sequence counter, a map from `(sender, client_message_id)` to immutable records, and per-recipient mailbox lists. No users table, logins, or tokens.

Run one Uvicorn worker. One `asyncio.Lock`, encapsulated in the store, guards every read and write. Inside the lock: in-memory work only, never I/O, sleeps, or JSON serialization. Epoch and clock may be injected for tests.

## Accept or replay

`accept_or_replay(expected_epoch, message)` must:
1. Validate and canonicalize the message before taking the lock.
2. Under the lock, check the epoch.
3. If the key exists with the same payload, return the original record unchanged: same sequence and timestamp, no new mailbox entry.
4. If the key exists with different content, return a conflict and change nothing.
5. Otherwise allocate a sequence, build one record, and add it to both the key map and the recipient mailbox.
6. Release the lock, then serialize the stored record.

First acceptance and exact retry both return 200 with identical bodies. The sender is part of the key, so different senders may reuse a UUID. Self-sent messages appear once. Never special-case test users or fixture IDs.

## Read inbox

`read_inbox(expected_epoch, recipient, after, limit)` checks epoch and cursor, then takes one snapshot of messages with sequence greater than `after`, ordered by sequence, reading `limit + 1` to set `has_more`. `next_cursor` is the last returned sequence, or `after` if empty. Never jump the cursor to the global latest sequence. Reads never delete or modify records, and callers must not be able to mutate stored data through returned objects.

## Validation

Read exact limits from the spec; do not define new ones here.
- Canonicalize usernames exactly as specified: no locale-aware casing or extra Unicode folding.
- Preserve text exactly and measure its limit in UTF-8 bytes. Reject invalid strings rather than replacing characters.
- Reject booleans, floats, and numeric strings where an integer is required; validate UUID format and integer ranges.
- Reject unknown request fields; add no aliases.
- Invalid requests never allocate sequences or leave partial records.
- Do not trust FastAPI's default coercion or error format; configure schemas explicitly.

## Errors

All failures, including malformed JSON and FastAPI validation errors, use the one envelope from the spec (`code`, `message`, `server_epoch`) with no Pydantic-shaped errors or stack traces. Mappings are in design section 5. Unexpected failures stay failures, never empty successes. Do not log full message bodies by default.

## Lifetime and configuration

Keep messages and duplicate keys until exit. Add no eviction, delete or reset endpoints, or delivery acks; tests that need a fresh session start a new server. A restart creates a new epoch and empty state. Disable auto-reload for recorded test runs. Host and port come from configuration, never hard-coded. Use `GET /v1/meta` as the readiness check. No CORS, cloud services, auth, databases, queues, or messaging SDKs.

## Required checks

B01 is done only when each has a recorded passing result:
- The single-worker server starts; `/v1/meta` returns the version and one stable epoch.
- A new message is accepted and appears in the recipient's inbox.
- An exact retry returns the original sequence and timestamp, with one inbox entry.
- Concurrent identical submissions produce one record; a conflicting key yields one winner and a conflict, with indexes intact.
- The sender is part of the key; mailboxes are isolated; unregistered recipients and self-send work.
- Paging works across multiple pages, gaps, empty pages, exclusive cursors, and repeated reads.
- Invalid names, UUIDs, UTF-8 sizes, types, unknown fields, headers, and query values are rejected with no state change.
- Malformed JSON and validation failures use the standard error envelope.
- A new server has a new epoch; stale-epoch requests fail without changing state.
- An accepted message whose response was lost can be retried without creating a duplicate.
- Separate app instances share no state.

Test route behavior in-process, and also run a smoke test against the real listening server. For concurrency, assert the invariant rather than which request wins. Inject faults in test code, never through production endpoints. These checks prove server behavior only; cross-client behavior is X01.

## AGENTS.md files

Any new subdirectory added under `backend/` must include its own `AGENTS.md` that:
- References this file and root `AGENTS.md` as parents.
- Describes the subdirectory's scope, layout, and commands.
- Lists verified commands with working directory and exit status once they pass.

Update this file whenever a task changes the layout, commands, or conventions for `backend/`.

## Done

Review the diff and confirm only `backend/` changed. Commit coherent increments. Hand off per root `AGENTS.md`, listing any proposed spec changes.