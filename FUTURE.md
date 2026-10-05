# Future

What I would do next, given more time.

## Spec and protocol

- **Reactions.** A new event type (`reaction`) with a `target_event_id` and an emoji body. Most of the things like envelope, sync engine, and storage transactions are unchanged; only a new type registration and display rule are needed. This would be the first real test of the evolution path.
- **Attachments.** A `message.file` event type with a pre-upload step before submission. Requires a new API endpoint and an additional outbox state, but no changes to the pull or cursor logic.
- **Group conversations.** This is the expensive one: addressing changes from a per-user mailbox to a per-conversation mailbox, which requires a protocol version change. The design notes this limit openly.
- **Resolve restart recovery** The spec currently leaves open what happens to queued events when the server restarts and the epoch changes. Defining that case would unblock MT5 test coverage and make the reset flow fully specified.

## Verification

- **Automated native checks.** The current harness drives headless runners; the native app checks are manual. XCTest UI tests and Espresso tests would close that gap.
- **Fault injection test** The test currently controls the network via a runner flag. Intercepting at the HTTP level would let the harness inject faults without any runner cooperation, making fault coverage independent of the generated code.
- **Continuous verification.** Run `/verify` automatically on every change in CI, with results posted back to the task ledger.

## Server

- **Persistent storage.** The in-memory server loses state on restart. SQLite persistence would let the server restart recovery spec (SPEC02) be tested without a dedicated fault injection path.
- **Auth stub.** Even a simple shared secret per username would let the spec define what happens when a client uses the wrong identity, which is currently out of scope.
