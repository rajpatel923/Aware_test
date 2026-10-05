# Design

This document explains how the repository is shaped and why. It does not define behavior: every requirement lives in `spec/`, and where this document mentions one it cites the rule ID. If this document and the spec disagree, the spec wins and this document is wrong.

## 1. What is being built

The deliverable is a **spec-driven code generator**: a written specification plus an agentic harness that turns it into working client code. A small messaging app is the example. It has one server and two clients in languages that cannot share source, Swift (iOS) and Kotlin (Android), which must behave identically.

The core promise: delete the generated client code, run the generator, and get back working clients whose behavior matches the spec. Every decision below serves that promise or one of the assignment's other evaluation criteria.

#### Regeneration Works
- Disposable generated code
- Clearly declared generation boundary
- Generate code from `spec/` only
- See Sections 3 and 7

#### Spec Is Authoritative
- Use Rule IDs
- Assign one owner per topic
- Include rule citations in code
- See Section 4

#### Two Clients Interoperate
- Build independent client implementations
- Verify both clients against each other over real HTTP
- See Sections 7 and 8

#### Evolution
- Use typed events
- Define a clear extension recipe for future changes
- See Sections 5 and 9

## Quality
- Use deterministic Gherkin scenarios
- Test role swapping
- Include fault injection
- Provide honest, reproducible evidence
- See Section 8

## 2. Principles

1. The spec is the only source of behavior. Code, tests, and agents derive from it. When the spec is silent or contradictory, agents stop and report rather than guess.
2. Generated code is disposable. Nothing of value may exist only in generated files. A fix to generated behavior is a fix to the spec or the generator.
3. Implementations stay independent. The Swift and Kotlin clients are each generated from the spec without seeing the other. If they then interoperate, the spec was precise enough. If one were translated from the other, interoperability would prove nothing.
4. Every behavior is traceable. Rules have stable IDs (`D…`, `P…`, `O…`, `T…`, `A…`), and generated code cites them. Any line of client logic can be traced to the rule that requires it.
5. Verification is deterministic. Tests drive clients through explicit commands. No step sleeps, and no assertion depends on timing or generated IDs.
6. Local first.Every user action succeeds against local storage; the network only syncs. Offline is the normal case, not an error path.
7. Extend by adding, not rewriting. New features arrive as new event types with their own rules, leaving the envelope and sync machinery untouched.
8. Evidence over claims. A check that did not run is reported as NOT RUN. A missing toolchain is never a pass.

## 3. Repository

- `spec/`: the source of truth.
- `generator/` and `.agents/skills/`: the harness that turns the spec into clients. 
- `.agents/`: task tracking, workflow, skills, and the generation boundary. 
- `AGENTS.md`, `CLAUDE.md`: agent instructions.
- Server: a small process / backend code.
- Cross-client test harness: hand-written, because it is the oracle. Generated code must never be able to rewrite the thing that judges it.
- iOS and Android clients: generated.

Generated paths are `clients/ios/` and `clients/android/`. Everything else is protected from deletion and overwriting by generation.

## 4. Specification structure

The spec is split by concern, and each topic has exactly one owning file:

- `product.md`: purpose and user-facing requirements
- `domain.md`: entities, value rules, statuses
- `protocol.md`: the messaging protocol, independent of HTTP
- `api.md`: the HTTP wire format
- `offline-behavior.md`: outbox, sync cycle, retries, lifecycle
- `ui.md`: screens and display
- `test.md`: runner contract, scenarios, fixtures
- `platform/ios.md`, `platform/android.md`: platform choices and commands


**Why the protocol is separate from the API.** The protocol (idempotency, sequencing, cursors) is the hard part and is transport-independent. If polling were replaced with WebSockets, `api.md` would change and `protocol.md` would not.

**Why platform files are separate.** Shared behavior must be identical across languages; platform choices (storage library, UI framework, build commands) legitimately differ. Keeping them apart makes it obvious which rules both clients must share.

## 5. Protocol decisions

- **Typed events instead of plain messages** (`protocol.md` P2, P3). Every exchange is an envelope with a `type` and a type-specific `body`. Text messages are type `message.text`. This is the main extension point: reactions or attachments become new types without changing the envelope, endpoints, or sync logic.
- **Client-generated IDs and idempotent submission** (P5, P6). The client creates each event's ID before storing it and reuses it on every retry; the server accepts each `(sender, event_id)` once. This makes "retry until it works" safe, which is what lets an offline queue flush without duplicates when a response is lost.
- **Server sequence numbers define order** (P6.3, P8). Device clocks disagree, so ordering never uses timestamps. The server's sequence is the single shared order both clients display.
- **Cursor-based pull** (P7). Each client keeps the highest sequence it has stored and asks for anything after it. The server never deletes on read, so a lost response is simply pulled again. Page and cursor commit together, so a crash never skips or duplicates.
- **Server epoch** (P4, P10). The in-memory server loses everything on restart. The epoch lets clients detect that instead of reusing a cursor that no longer means anything.
- **Polling, not push.** Short polling has fewer connection states than WebSockets and makes replay trivial. The cost is a second of latency and some empty requests, which is acceptable for a local example.
- **Pull before submit** (`offline-behavior.md` O5.3). This fixes the order of events in the assignment's final step, so both clients produce the same trace, not just the same end state.
- **Strict requests and responses** (`api.md` A1.6). The server rejects unknown request fields; clients ignore unknown response fields. The server can grow without breaking older generated clients.

## 6. Client architecture

Each client is a UI-independent **core** with **adapters** around it:

- The core holds the domain, protocol, and sync logic and depends only on interfaces (storage, transport, clock, ID source).
- Adapters implement those interfaces with real libraries: SQLite for storage, the platform HTTP client for transport.
- Two thin entry points use the same core: the native app (SwiftUI or Compose) and a **headless runner** driven by tests.

**Why a core.** All behavior worth verifying lives in one place per language, and tests exercise exactly the code the app runs.

**Why a headless runner.** Simulators and emulators are slow and hard to script. A runner speaking a small JSON command protocol (`test.md` section 2) lets one harness drive both languages identically. It proves behavior, not native integration, which is tested separately (T1.3).

**Why SQLite.** Offline correctness depends on a few writes being atomic: storing a message with its outbox entry, recording acceptance while removing the entry, and storing a page with its cursor (`offline-behavior.md` O11.2). SQLite transactions give that directly on both platforms. Specific libraries are chosen in the platform files.

## 7. Generator and harness

The harness separates analysis, implementation, and verification into four roles (`AGENTS.md`):

1. **Specification Analyzer** reads the spec, lists affected rules by ID, flags gaps, and records a plan in `.agents/TASKS.md`. It writes no code.
2. **iOS Implementer** and 3. **Android Implementer** each generate one client from the spec and their platform file. Neither may read the other's code (principle 3).
4. **Verifier** builds both clients, runs every scenario in both role assignments against the real server, and reports violations by rule ID. It cannot edit code, spec, or tests.

**Why roles.** An agent that writes code and then judges it tends to grade itself generously. Separating the verifier, and forbidding it from editing, keeps the oracle honest. Separating the analyzer surfaces spec gaps before code is written, when they are cheap to fix.

**Why generate from spec only.** If the generator could read old generated code, regeneration would copy rather than derive, and the core promise would be untested. Generation therefore uses only `spec/` and declared inputs, never earlier output or its history.

**Invocation.** The generator is one documented command per platform that runs the roles in order with the inputs above, then the Verifier. Where the tooling allows, each implementer runs with only `spec/` and its own output path visible, so isolation is enforced rather than requested. The exact commands, tool, and working directory are documented in the README.

## 8. Verification

- **Fixtures** (`test.md` section 6): username and text edge cases that commonly diverge between languages, such as Unicode case rules and UTF-8 byte counting.
- **Unit tests** per client, with injected transport and clock for cases the cross-client harness cannot produce (`test.md` section 7).
- **Cross-client scenarios** (`test.md` section 5): Gherkin scenarios using a fixed step vocabulary, each run twice with the languages swapped between Alice and Bob. They include the assignment scenario plus lost acknowledgements, lost pages, and restarts.
- **Native checks**: each app builds and runs the main flow. A headless pass alone does not count.

## 9. Evolution

A new feature follows a fixed path: register the event type in `protocol.md`, define its body in `domain.md`, its display in `ui.md`, and its scenarios in `test.md`, then regenerate. The envelope, endpoints, sync cycle, and storage transactions stay the same, so a well-specified reaction or attachment type should regenerate into working clients without harness changes.

Some features are deliberately not that cheap. Group conversations change addressing (who a mailbox belongs to and who may read it), so they require a protocol version change (P3.9). The design states this limit openly rather than pretending everything is additive.

## 10. Tradeoffs and limitations

- **In-memory server.** A restart loses undelivered events. Clients detect it via the epoch but cannot recover what the server lost.
- **No authentication.** Usernames identify mailboxes but prove nothing; any client can read any mailbox.
- **Foreground-only sync.** Mobile operating systems do not guarantee background execution; v1 promises nothing while an app is suspended.
- **One device per username.** Two devices with the same name would each see only their own sent history.
- **Polling latency** of about a second while active.
- **Agent output is not byte-identical across runs.** Regeneration is judged by conformance to the spec and passing scenarios, not by matching earlier output.

## 11. Open decisions

- **Server restart recovery** (`protocol.md` P10.3, `offline-behavior.md` O9.2): how a client leaves the reset state and what happens to queued events.
- **Generator invocation** (section 7): the exact command and tool the evaluator runs.