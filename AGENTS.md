# AGENTS.md

Instructions for AI coding agents working in this repository. This file is self-sufficient: an agent that reads nothing else must still follow the project rules correctly.

## Project overview

A local messaging app: one Python/FastAPI chat server and two independent clients, Swift (iOS) and Kotlin (Android). Both clients must behave identically against the same server. They share the HTTP contract and test fixtures, never messaging code.

Required behavior (never weaken):
- Identify the user by name on first launch.
- Send text addressed to another user.
- Queue outgoing messages locally while offline; flush them after reconnection.
- Display messages received from the server.

Constraints: runs fully locally, no hosted services, no turnkey messaging SDKs, general-purpose HTTP/JSON/storage libraries only. Small single-process server; no production auth, cloud, or distributed infrastructure. Never hard-code the test conversation into application behavior.

## Repository layout

| Path | Purpose |
|---|---|
| `spec/behavior.md` | Messaging behavior and failure rules (authoritative) |
| `spec/protocol.openapi.yaml` | HTTP contract (authoritative) |
| `.agent/design.md` | Architecture and tradeoffs |
| `.agent/task.md` | Task order, acceptance checks, progress |
| `backend/` | FastAPI server |
| `ios/` | Swift core, adapters, SwiftUI app, headless runner |
| `android/` | Kotlin core, adapters, Compose app, headless runner |
| `tests/` | Cross-client acceptance tests. Never rewrite to hide a failure. |
| `backend/AGENTS.md`, `ios/AGENTS.md`, `android/AGENTS.md` | Platform conventions |

Every path above is planned. Confirm a file exists before relying on it.

## Architecture

| Area | Baseline |
|---|---|
| Server | Python, FastAPI, one process and worker, in-memory mailboxes and duplicate tracking |
| iOS | Swift messaging core, SwiftUI shell, URLSession adapter, SQLite via GRDB, headless Swift runner |
| Android | Kotlin messaging core, Compose shell, OkHttp adapter, SQLite via SQLDelight, headless JVM runner |
| Transport | HTTP/JSON with cursor-based polling |
| Boundaries | Core owns all messaging behavior; network and storage are injected; UI and headless runners stay thin |

Each client's app and headless runner use the same core and the same real adapters. Headless does not mean continuous background execution on a phone.

## Source of truth (highest wins)

1. The user's explicit instructions in this session
2. `spec/`
3. `.agent/design.md`
4. `.agent/task.md`
5. Platform `AGENTS.md` files (conventions only; never change the shared protocol)
6. Existing code and test results. Never the authority for ambiguous behavior.

On a conflict, stop the affected work and report both paths, the conflicting lines, and a proposed resolution. Never weaken an acceptance check to match the code.

## Working rules

**Grounding**
- Cite the path you read this session for every claim about the repo; otherwise say "not verified".
- Confirm any file, command, flag, package, version, or API exists before using it. If you cannot, label it `UNVERIFIED:` and do not execute it.
- Read dependency versions from lockfiles or build files, never from memory.
- Never report a check as passed without output from this session. Never fabricate commits or results.

**Missing or unclear inputs**
- Missing input: do not invent it. Report the path and what depends on it; continue independent work.
- Requirement ambiguity: ask. If no human is available, stop that task and record the question in the handoff.
- Implementation choice the spec does not constrain: decide, and list it under Assumptions.

**Scope**
- Do only what the current request covers. A request for one file authorizes only that file.
- Within an authorized implementation task, make routine choices without asking again.

## Task workflow

1. Run `git status` and preserve existing changes.
2. Find the task in `.agent/task.md`: prerequisites, files it owns, acceptance checks.
3. Read the relevant `spec/` and `.agent/design.md` sections and the platform `AGENTS.md` for each folder you edit.
4. Make the smallest coherent change. Platform details stay in adapters and UI.
5. Run the relevant checks from their real working directory.
6. Review the diff.
7. Record evidence in the task entry and write the handoff.

Prerequisites: client work needs the HTTP contract in `spec/`; cross-client tests need the real server and both real clients.

## Behavioral invariants

`spec/` holds exact fields and limits and wins on conflict.

- **Enqueue:** save the message and its outbox entry in one transaction before reporting it queued. Retries reuse the original ID and payload.
- **Server acceptance:** duplicate check and acceptance are one protected operation. An identical retry returns the original acceptance; reusing an ID with different content is rejected.
- **Acknowledgement:** mark accepted and remove the outbox entry in one transaction. Accepted means the server has it, not that the recipient read it.
- **Receive:** save each page of messages and its cursor in one transaction. Deduplicate. Never advance the cursor from a send acknowledgement or device clock.
- **Server restart:** detect that the server restarted; never reuse a cursor from a previous server instance.
- **Sync:** one active sync per client. Network-change callbacks are hints only. Cancelling a sync keeps pending messages. No database transaction spans a network call.

## Testing

**Mandatory Alice/Bob scenario**
1. Alice and Bob exchange messages while both are online.
2. Both disconnect, and each queues one message.
3. Alice reconnects and sends hers.
4. Alice disconnects again.
5. Bob reconnects, receives Alice's message, and sends his.
6. Alice reconnects and receives Bob's message.

When Bob sends in step 5, offline Alice has not received it yet; only step 6 proves receipt. Run with the real Swift client, the real Kotlin client, and the real server, then swap which language plays Alice and Bob. Fake in-memory clients do not count.

**Other required checks**
- Both clients parse the shared scenarios in `spec/scenarios/` identically.
- Storage tests against real SQLite: enqueue, acknowledgement, receive, and restart with queued messages.
- Server tests: duplicate handling, routing, pagination, restart detection.
- A lost send response and a repeated inbox page cause no lost or duplicated message.
- Real native builds of both apps.

**Reporting:** every check is PASS, FAIL, or NOT RUN, with the exact command, working directory, and exit status. A missing Xcode or Android toolchain means NOT RUN. A passing headless test does not prove the native app works.

## AGENTS.md files

Every directory introduced by an agent must include its own `AGENTS.md`. The file must:
- State which parent `AGENTS.md` it refines and instruct readers to read both.
- Describe the directory's scope, layout, and any conventions that differ from the parent.
- List verified commands (with working directory and exit status) once they pass; leave them blank until then.

Existing `AGENTS.md` files must be updated whenever a task changes a directory's scope, layout, or commands. An agent that creates a new subdirectory and omits its `AGENTS.md` has left the task incomplete.

## Git

- Commit coherent increments; stage only intended files.
- Never fabricate or rewrite history.
- Never commit secrets, local databases, or build output.

## Handoff

End every task with:
- **Changed:** files touched
- **Verified:** each check as PASS / FAIL / NOT RUN
- **Assumptions:** choices made without a spec constraint
- **Gaps:** missing inputs, with paths
- **Next:** the next task, named but not started