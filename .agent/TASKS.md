# Tasks

Ordered work for the spec-driven generator, with status and evidence. Procedures are in `.agent/WORKFLOW.md`; roles in `AGENTS.md`.

**Statuses:** `pending` (not started), `in_progress` (started), `blocked` (cannot proceed; names the missing input and next action), `done` (completion evidence recorded below). A task is eligible when its dependencies are `done`.

**Order principle:** prove the riskiest part first. Regeneration is the primary grading criterion and the generator does not exist yet, so a thin end-to-end generator slice (G01) comes before finishing the remaining spec files. Spec work after that is shaped by what the generator actually needs.

## Register

| ID | Status | Depends on | Role | Output |
|---|---|---|---|---|
| H01 | pending | none | author | Rename `spec/platform/andriod.md` → `android.md` |
| H02 | pending | none | author | Define H02 task (referenced by G01 but undefined — see S01 findings) |
| H03 | pending | none | author | Remove obsolete files from earlier drafts, if present |
| H04 | pending | H01, H03 | author | Commit existing work in logical steps |
| D01 | done | none | author | Server-restart recovery accepted: P10.3 and O9.2 updated, [DECISION NEEDED] removed |
| D02 | done | none | author | Generator invocation: slash commands in `skills/`, documented in README |
| D03 | done | none | author | snake_case wire names confirmed; `INTERNAL_ERROR` in `api.md` section 4 |
| S01 | done | D01, D03 | Analyzer | Spec consistency pass complete; findings below; all gaps have tasks |
| S02 | pending | H01 | author | `spec/platform/ios.md` (file already exists; task is to review/complete it) |
| S03 | pending | H01 | author | `spec/platform/android.md` |
| S07 | pending | S01 | author | Fix T2.1: add `local_order` and `epoch` to snapshot field list in `test.md` |
| S08 | pending | S01 | author | Fix T2.5: correct `O10.1a` cross-reference to `O10.1` in `test.md` |
| S09 | pending | S01 | author | Fix stale "pending P10.3" label on `reset_session` row in `test.md` section 2 |
| E01 | pending | none | author | Toolchain inventory |
| G01 | pending | D02, H02, S02 or S03, E01 | author | Generator thin slice |
| B01 | pending | S01 | author | Server |
| V01 | pending | S01 | author | Cross-client test harness |
| S04 | pending | S01 | author | `spec/product.md` |
| S05 | pending | S01 | author | `spec/ui.md` |
| S06 | pending | D01 | Analyzer | Scenario S5 (server restart) in `test.md` |
| G02 | pending | G01, S02, S04, S05 | iOS Implementer | Full iOS client generated |
| G03 | pending | G01, S03, S04, S05 | Android Implementer | Full Android client generated |
| X01 | pending | G02, G03, B01, V01 | Verifier | All scenarios pass, both role assignments |
| N01 | pending | G02 | Verifier | iOS app builds and runs main flow |
| N02 | pending | G03 | Verifier | Android app builds and runs main flow |
| R01 | pending | X01, P01 | Verifier | Clean regeneration proven (W6) |
| EV1 | pending | R01 | author | Optional: extension demo |
| P01 | pending | X01 | author | README |
| P03 | pending | R01, P01 | author | Delivery archive with history |

## Details

**H01. Rename the Android platform file.** `AGENTS.md`, `CLAUDE.md`, `DESIGN.md`, and `test.md` all reference `spec/platform/android.md`. Done when the file has the correct name and nothing references the misspelling.

**H02. Define or remove the H02 dependency.** G01 lists `H02` as a dependency but no task with that ID exists in the register. Done when H02 is either defined (e.g., a specific prerequisite for the generator thin slice such as a DESIGN.md entry or README stub) or removed from G01's dependency list with a note explaining why.

**H03. Remove obsolete drafts.** Earlier versions (a chat-only `AGENTS.md`, `design.md`, `task.md`, `protocol.openapi.yaml` for `/v1/messages`, old `scenarios/`) contradict the current spec. Done when no file describes a different API, layout, or scope.

**H04. Commit existing work.** Commit history is graded. Commit instruction files, `DESIGN.md`, and each spec file as separate commits with honest messages, including that drafts were written with AI assistance. Done when `git log` shows the work in steps.

**D01. Server-restart recovery.** ✓ Resolved. P10.3 and O9.2 updated: explicit reset action adopts the new epoch and sets cursor to 0; outbox entries resubmit with original envelopes.

**D02. Generator invocation.** ✓ Resolved. Generator is a set of Claude Code slash commands backed by skill files in `skills/`. Evaluator runs `/analyze`, `/generate-ios`, `/generate-android`, `/verify` in Claude Code. Documented in README.

**D03. Wire naming and error code.** ✓ Resolved. All wire names are snake_case. `INTERNAL_ERROR` is in `api.md` section 4.

**S01. Spec consistency pass.** Analyzer reads all spec files together and lists every contradiction, undefined term, or rule without a test. **Done.** All gaps below now have tasks.

*Files read:* `spec/product.md`, `spec/domain.md`, `spec/protocol.md`, `spec/api.md`, `spec/offline-behavior.md`, `spec/ui.md`, `spec/test.md`, `spec/platform/ios.md`, `spec/platform/andriod.md`.

*Affected rules (all platforms unless noted):*
- Shared: D1–D9, P2–P11, A1–A5, O1–O11, U1–U7, T1–T4, S1–S4
- iOS only: I1–I8
- Android only: K1–K8
- Server: P6, P7, A3, A4

*Acceptance scenarios that must pass:* S1 (both role assignments), S2, S3, S4. S5 pending S06/S07/S08/S09.

*Blockers resolved by new tasks:*

1. **`spec/platform/andriod.md` filename typo** → H01 (pre-existing). Blocks S03 and W2 Android generation. Every reference in `AGENTS.md`, `CLAUDE.md`, `DESIGN.md`, `spec/test.md`, and `.agent/WORKFLOW.md` uses the correct spelling `android.md`; the file itself is misspelled. Until renamed, the iOS platform file (`spec/platform/ios.md`) is the only platform file reachable by its documented path.

2. **S5 scenario body not written** → S06 (pre-existing). D01 resolved P10.3 and O9.2, removing the `[DECISION NEEDED]` blocker, but the executable Gherkin for S5 in `test.md` is still a placeholder. Rules P10.1–P10.3, O9.1–O9.2 have no cross-client test coverage.

3. **T2.1 snapshot field list is incomplete** → S07 (new). `test.md` T2.1 lists snapshot event fields as: `event_id`, `type`, `sender`, `recipient`, `body`, `seq`, `accepted_at`, `direction`, `status`, `failure_code`. Missing from this list: `local_order` and `epoch`, both defined as local event fields in `domain.md` section 5. Clients implementing the snapshot command must include these or the runner contract is underdefined. **Impact:** `domain.md` D5.1 (local_order), D8.1 (epoch/cursor invariant), and O4.1 (epoch stored on acceptance) cannot be verified through the headless harness.

4. **`O10.1a` sub-rule reference does not exist** → S08 (new). `test.md` T2.5 says "Runners start in manual mode (`offline-behavior.md` O10.1a)". `offline-behavior.md` has O10.1 but no sub-rule `a`. The reference is dangling.

5. **`reset_session` row labeled "pending `protocol.md` P10.3"** → S09 (new). In `test.md` section 2 runner-command table, the `reset_session` row carries a "pending P10.3" annotation in the result column. D01 resolved P10.3 (recovery decision made, O9.2 updated). The annotation is stale and implies the command is optional; it should be removed so implementers know it is required.

6. **H02 undefined in G01 dependency** → H02 (new). See H02 detail.

*Questions with assumed defaults (non-blocking):*

Q1. **`server_epoch` in pull response: top-level vs per-event.** The pull response has `server_epoch` at the top level and also inside each event object. `protocol.md` P2.1 does not list `server_epoch` as an envelope field; P7.3 says clients verify the epoch matches. *Assumed default:* clients read `server_epoch` from the top-level response for epoch verification; the per-event `server_epoch` is redundant and permitted per A1.6 ("clients ignore unknown fields in responses"). No spec change needed.

Q2. **T2.6 appears after T2.7 in `test.md`.** The rules are numbered out of order in the document (T2.7 `sync_once` precedes T2.6 restart behavior). Content is unambiguous. *Assumed default:* renumber in a future spec-only pass (W1); content is authoritative today.

Q3. **iOS runner binary named `messaging-runner`; Android runner named `runner`.** The test harness (V01) must know both names to start runners. Neither `test.md` nor the step vocabulary specifies binary names. *Assumed default:* V01 reads the binary name from each platform file (I8.1, K8.1) rather than hardcoding; no spec change needed.

*Missing tests (no executable coverage yet):*

- MT1: P10.1–P10.3, O9.1–O9.2 (server restart full flow) → blocked on S06 (S5 scenario body).
- MT2: `local_order` and `epoch` in snapshot → blocked on S07 (T2.1 fix).
- MT3: `failure_code` value for each permanent-rejection code (`INVALID_REQUEST`, `UNSUPPORTED_TYPE`, `EVENT_ID_CONFLICT`) is covered in `test.md` section 7 client-only checks only implicitly. No fixture asserts the exact code stored. Consider adding to section 7 in a future pass.

**S02 / S03. Platform files.** For each platform: language and minimum OS, UI framework, storage and HTTP libraries with pinned versions, module or package layout, headless runner start-up flags (`test.md` T2.5), host address for reaching the server from a simulator or emulator, development-only cleartext settings, disabling HTTP auto-retry (`api.md` A5.2), and the exact build, test, and runner commands. Commands are marked unverified until run in E01 or G01. Done when an implementer could start without asking a question.

**E01. Toolchain inventory.** Record versions of Python, Xcode and Swift, JDK, Gradle, Android SDK and emulator, and the agent tool, each as available, missing, or untested, with the commands used. macOS is required for anything iOS. Done when recorded below.

**G01. Generator thin slice.** Build the smallest real generator: the documented command runs the agent on one platform and generates only the domain validation from `domain.md` (usernames and `message.text`) with unit tests for the fixtures in `test.md` section 6. Then delete the output and regenerate. Done when the slice regenerates from a clean state and its tests pass twice. This proves the pipeline before the rest of the spec depends on it.

**B01. Server.** Hand-written, single process, in-memory, implementing `api.md` and `protocol.md` sections 4, 6, 7, and 10. Done when server tests cover idempotent acceptance, conflicts, routing, paging, validation order, epoch mismatch, and the error envelope.

**V01. Test harness.** Hand-written. Parses the Gherkin in `test.md`, starts a fresh server and both headless runners, maps each step to runner commands per the step vocabulary, and records transcripts. Done when it runs a scenario against a deliberately wrong fake runner and correctly reports the failure.

**S04 / S05. Product and UI specs.** `product.md`: the user-facing requirements from the assignment and what is out of scope. `ui.md`: identify screen, conversation screen, status display for each state in `domain.md` section 6 and `offline-behavior.md` section 7, unknown event type placeholder, error display. Done when every displayed state has a defined presentation.

**S06. Server-restart scenario.** Write S5 in `test.md` from the D01 decision. Minimum assertions per the existing placeholder: after a server restart the syncing client reaches state `server_reset`, keeps every local event, and does not use its old cursor. Full coverage should also assert: reset action adopts new epoch and sets cursor to 0 (P10.3), outbox entries resubmit with original envelopes (O9.2), and events previously accepted by the old session that the client already holds are not duplicated (P7.5).

**S07. Fix T2.1 snapshot field list.** Add `local_order` and `epoch` to the `events` field list in `test.md` T2.1. Both are defined in `domain.md` section 5 as persisted local-event fields. For queued events, `epoch` is null and `seq` is null; for accepted events both are non-null. Done when T2.1 explicitly lists all seven local-event fields from `domain.md` section 5.

**S08. Fix T2.5 cross-reference.** Change `O10.1a` → `O10.1` in `test.md` T2.5. Done when no dangling sub-rule reference remains.

**S09. Remove stale "pending P10.3" annotation.** In `test.md` section 2, the `reset_session` result column contains "(pending `protocol.md` P10.3)". D01 resolved P10.3. Remove the annotation so the command is unambiguously required. Done when the table row has a clean result definition.

**G02 / G03. Full clients.** Run W2 for each platform. Done when the client builds, its unit tests pass, its headless runner implements `test.md` section 2, and every generated behavior cites its rule IDs.

**X01. Cross-client verification.** Run W3. Done when every scenario in `test.md` passes in both role assignments, with transcripts recorded.

**N01 / N02. Native checks.** Build and run each app on a simulator or emulator: identify, send, receive, queue offline, reconnect and flush, relaunch with data intact. A missing toolchain makes the task `blocked`, never `done`.

**R01. Clean regeneration.** Run W6. Done when a fresh clone, with generated paths deleted and only the README followed, regenerates both clients and passes X01.

**EV1. Extension demo (optional, strong signal for "Evolution").** On a branch, add a small event type such as `reaction.add` through W7 and regenerate with no generator changes. Record the result, success or failure, in `DESIGN.md`.

**P01. README.** Initial draft added; expand once server and clients are built and verified. Must include: the generator commands, the generated code location, how to run the server, how to run verification, and attribution. Per assignment requirements.

**P03. Delivery.** Archive the repository with full git history.

## Evidence

Record one entry per attempt: task ID, date, commit, tool and versions, exact command, working directory, exit status, result, log location, and limitations.

No evidence recorded yet.