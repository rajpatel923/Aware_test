# SPEC01 — Specification analysis

Written by the Specification Analyzer (`AGENTS.md`) before generation. This report is not a generator input and defines no behavior: only `spec/` does. Task status lives in `.agents/TASKS.md`; check results in `.agents/evidence/LEDGER.md`.

## Run

- Date: 2026-10-05 (third pass; second pass at commit e294ff7; first pass at commit 26858250)
- Repository commit: e294ff7811c3fe5d49236ab8f0b3b9db49710e3c
- Spec revision: same commit — includes O10.6–O10.8, U4.1 rewrite, S6 scenario, K1.3 update
- Agent tool and version: Claude Sonnet 4.6 via `/analyze` skill
- Requested change or scope: Full spec re-analysis; no spec changes since previous pass; verify conclusions hold and check for newly found issues

## Rules

- List only rules affected by the requested scope, by ID. Do not list every rule in the spec.
- A gap the analyzer fills with an assumption is a **question**, not a resolution. Record the proposed default and mark it unapproved.
- A question that changes shared behavior blocks generation of that behavior until it is resolved through the spec-change workflow (`.agents/WORKFLOW.md` W1).
- A question that is only a free implementation choice may proceed; say so explicitly.
- Never report "no blockers" while any question is unresolved.

## Affected rules

**Shared (both clients):**

Domain: D1.1, D1.2, D1.3, D2.1, D3.1, D3.2, D3.3, D4.1, D4.2, D4.3, D5.1, D5.2, D5.3, D6.1, D6.2, D6.3, D6.4, D7.1, D8.1

Protocol: P2.1, P2.2, P2.3, P2.4, P2.5, P3.1, P3.2, P3.3, P3.4, P3.5, P3.6, P3.7, P3.8, P3.9, P4.1, P4.2, P4.3, P4.4, P5.1, P5.2, P5.3, P5.4, P5.5, P5.6, P5.7, P6.1, P6.2, P6.3, P6.4, P6.5, P6.6, P7.1, P7.2, P7.3, P7.4, P7.5, P7.6, P7.7, P8.1, P8.2, P8.3, P10.1, P10.2, P10.3

API (client-side obligations): A1.1, A1.2, A1.3, A1.4, A1.5, A1.6, A2.1, A3.1, A3.3, A3.5, A3.6, A4.1, A4.2, A5.1, A5.2, A5.3

Offline behavior: O1.1, O1.2, O1.3, O2.1, O2.2, O2.3, O2.4, O2.5, O2.6, O3.1, O3.2, O3.3, O4.1, O4.2, O4.3, O4.4, O4.5, O4.6, O5.1, O5.2, O5.3, O5.4, O5.5, O6.1, O6.2, O6.3, O6.4, O7.1, O8.1, O8.2, O9.1, O9.2, O10.1, O10.2, O10.3, O10.4, O10.5, O10.6, O10.7, O10.8, O11.1, O11.2, O11.3

UI: U1.1, U1.2, U1.3, U2.1, U2.2, U2.3, U3.1, U3.2, U3.3, U3.4, U4.1, U4.2, U5.1, U5.2, U6.1, U6.2, U7.1, U7.2, U7.3, U7.4

Test: T1.1, T1.2, T1.3, T2.1, T2.2, T2.3, T2.4, T2.5, T2.6, T2.7, T3.1, T3.2, T3.3, T4.1, T4.2

**iOS only:**

I1.1, I1.2, I2.1, I2.2, I3.1, I3.2, I3.3, I3.4, I3.5, I4.1, I4.2, I4.3, I4.4, I5.1, I5.2, I5.3, I6.1, I6.2, I6.3, I7.1, I7.2, I7.3, I7.4, I8.1, I8.2, I8.3

**Android only:**

K1.1, K1.2, K1.3, K2.1, K2.2, K3.1, K3.2, K3.3, K3.4, K3.5, K4.1, K4.2, K4.3, K4.4, K5.1, K5.2, K5.3, K6.1, K6.2, K6.3, K7.1, K7.2, K7.3, K7.4, K8.1, K8.2, K8.3, K8.4

**Server (hand-written; clients must handle its responses):**

A3.2, A3.3, A3.4, A3.6, A3.7, P6.1, P6.2, P6.3, P6.4, P6.5, P6.6

## Questions

### Q1. `reset_session` semantics when client has not yet detected a new epoch — RESOLVED

- **Rules involved:** P10.3, O9.2, O10.7
- **Resolution (W1, 2026-10-05):** O10.6 establishes that sync state is never persisted. O10.7 specifies that on load (or after `reset_session` clears the stored epoch) the first sync cycle runs a session check (O5.2 step 1), which fetches the current server epoch. `reset_session` clears epoch to null and cursor to 0; the next cycle discovers the new epoch via the session check. This is now fully specified. No proposal required.

---

### Q2. Self-conversation display

- **Rules involved:** D5.2, domain section 9
- **Gap or contradiction:** D5.2 says a self-addressed event (sender = recipient = own identity) is stored once as `outgoing`. Domain section 9 defines a conversation as "the set of local events between this client's identity and one peer: events where the peer is the other party." When sender equals recipient there is no "other party." The spec does not define which conversation list a self-addressed event appears in, or whether a conversation "with self" is displayed.
- **Proposed default (unapproved):** The self-addressed event appears in a conversation whose peer is the client's own username (i.e., a conversation "with self"). The peer selector can address one's own username. This is a display-only choice and does not affect submission, acceptance, or any scenario in S1–S6.
- **Kind:** free implementation choice
- **Blocks:** nothing in S1–S6; MT3 test coverage if a self-send scenario is added later
- **Owner document for the fix:** `spec/ui.md` section 1.2 / `spec/domain.md` section 9

---

### Q3. Stopped sync state persistence across restarts — RESOLVED

- **Rules involved:** O7.1, O10.4, O10.6–O10.8, O11.1, U4.1, P10.2, P10.3
- **Resolution (W1, 2026-10-05):** Sync state is never persisted (O10.6). O10.4 now lists only data (identity, events, outbox, epoch, cursor). O10.7–O10.8 specify how each stopped state is re-derived on restart. U4.1 is rewritten to describe derived state. The contradiction is eliminated.

---

### Q4. Outbox `attempts` and `last_error` not observable via the headless runner

- **Rules involved:** O4.3, D7.1, T2.1
- **Gap or contradiction:** O4.3 requires the client to increment `attempts` and record `last_error` on each outcome-unknown submission failure. T2.1 specifies that `snapshot.outbox` lists `event_id`s only, not the full outbox entry. There is no runner command that exposes `attempts` or `last_error`, so conformance to O4.3's bookkeeping is unverifiable through cross-client tests.
- **Proposed default (unapproved):** O4.3's `attempts` and `last_error` fields are covered by client unit tests (injected transport returning timeouts). No cross-client scenario changes; the runner snapshot contract is left as-is.
- **Kind:** free implementation choice (client unit tests cover this without changing the runner contract)
- **Blocks:** nothing in S1–S6; MT2 coverage is incomplete until client unit tests are written
- **Owner document for the fix:** `spec/test.md` section 2 (if runner exposure is wanted) or client unit test plans

---

### Q5. Epoch separator display not tested (MT1)

- **Rules involved:** U3.4
- **Gap or contradiction:** U3.4 requires events from a previous server epoch to be shown with "a visual separator or epoch label." No scenario in test.md section 5 or client-only check in section 7 verifies that this separator is shown.
- **Proposed default (unapproved):** Clients implement U3.4 as a free display choice; coverage deferred to native UI review (N01/N02).
- **Kind:** free implementation choice (the form of the separator); missing test for behavioral correctness
- **Blocks:** nothing in S1–S6
- **Owner document for the fix:** `spec/test.md` section 5 or 7

---

### Q6. Post-restart cross-epoch history order not asserted in S5 (MT4)

- **Rules involved:** O9.2, U3.1, U3.4
- **Gap or contradiction:** In S5, after recovery Bob holds m1 (old epoch) and m2 (new epoch). S5 asserts only that Bob holds m2 as received; it does not assert the display order or the presence of m1 after recovery.
- **Proposed default (unapproved):** Bob's conversation shows m1 (old epoch) followed by the epoch separator followed by m2 (new epoch). Deferred to client unit tests or native review.
- **Kind:** free implementation choice (display only)
- **Blocks:** nothing in S1–S6
- **Owner document for the fix:** `spec/test.md` section 5 (S5 extended assertions) or section 7

---

### Q7. T2.6 / T2.7 numbering inversion (editorial)

- **Rules involved:** T2.6, T2.7
- **Gap or contradiction:** In `spec/test.md` section 2, T2.7 appears before T2.6. Both rules are correct in isolation; only the label order is inverted. No behavior is ambiguous.
- **Proposed default (unapproved):** Treat the rules in file order. An editorial fix to `spec/test.md` can re-number them without any behavioral change.
- **Kind:** editorial
- **Blocks:** nothing
- **Owner document for the fix:** `spec/test.md` section 2

---

### Q8. S6 Examples table lists unused `bob_lang` column

- **Rules involved:** T1.1, T1.2, test.md S6
- **Gap or contradiction:** Scenario S6 ("Server reset survives client restart") lists `bob_lang` in its `Examples` table but never starts Bob's client — `<bob_lang>` appears nowhere in the scenario body. T1.1 requires cross-client scenarios to use one client of each language; T1.2 requires each scenario to pass in both role assignments. As written, S6 uses only one language per run and does not satisfy T1.1's cross-client requirement.
- **Proposed default (unapproved):** S6 is intended as a single-client restart test; it is implicitly exempted from T1.1's cross-client requirement because it tests persistence behavior, not inter-client protocol. The `bob_lang` column should be removed from the Examples table, and S6 should run once per language (Swift-only, Kotlin-only) rather than twice as a pair. This is a purely editorial fix with no behavioral change.
- **Kind:** editorial (with a spec consistency question: is T1.1 meant to apply to S6?)
- **Blocks:** nothing in S1–S5; S6 can run as-is (unused column causes no test failure, just a linter warning)
- **Owner document for the fix:** `spec/test.md` S6 Examples table; optionally `spec/test.md` section 1 (T1.1) to carve out single-client scenarios

## Acceptance coverage

**Scenarios that must pass** (from `spec/test.md` section 5):

| Scenario | Rules exercised | Role assignments required |
|---|---|---|
| S1: Independent offline clients | D1.1, D2.1, D4.1–D4.2, O1.2, O2.3, O3.1, O4.1, O4.3, O5.1–O5.3, P5.1–P5.7, P6.1–P6.2, P7.1–P7.6, P8.1–P8.2 | Swift=Alice/Kotlin=Bob AND swapped |
| S2: Lost acknowledgement | P5.3, P5.4, P6.1, O4.3, T2.4 | Both role assignments |
| S3: Lost pull response | P6.5, P7.4, P7.5, T2.4 | Both role assignments |
| S4: Queue survives restart | O3.1, O10.4, O10.6, T2.6 | Both role assignments |
| S5: Server restart and recovery | P10.1–P10.3, O9.1–O9.2, O10.6 | Both role assignments |
| S6: Server reset survives client restart | O10.6, O10.7, O10.8, P10.2, P10.3 | Both role assignments |

**Client-only checks** (from `spec/test.md` section 7):

1. Unknown event type: stored, cursor advances, sync continues — P3.5
2. Invalid page (wrong recipient, non-increasing seq, bad cursor): commits nothing, enters `protocol_error` — P7.3
3. Mismatched acknowledgement: enters `protocol_error` — P5.5
4. Enqueue while submission in flight: succeeds — O2.5
5. Concurrent sync triggers: run one cycle; cancelled cycle results not committed — O6.1, O6.3
6. Client stopped in `protocol_error` or `incompatible`, then restarted: runs fresh session check on first cycle — O10.7, O10.8

**Coverage gaps** (rules in scope with no scenario, fixture, or client-only check):

| Rule | Behavior | Gap |
|---|---|---|
| U3.4 | Epoch separator in conversation view | MT1: no scenario or check; display-only — deferred to N01/N02 native review |
| O4.3 | `attempts` and `last_error` bookkeeping | MT2: not in snapshot; verifiable only by client unit tests with injected transport |
| D5.2 + domain section 9 | Self-conversation (sender = recipient) | MT3: no scenario; Q2 proposed default adopted as free choice |
| O9.2 + U3.1 + U3.4 | Cross-epoch conversation order after S5 | MT4: S5 does not assert Bob's full conversation display — deferred to native review |
| P3.3 | Server rejects unsupported type | Client refuses locally (O2.2) but the server rejection path has no cross-client test |
| O11.3 | Failed migration enters `storage_error` | Not testable via headless runner (no command to corrupt the schema) |

## Conclusion

- **Unresolved behavioral questions:** None that block generation. Q3 and Q1 are resolved by O10.6–O10.8. All remaining items (Q2, Q4–Q8) are free implementation choices, missing tests, or editorial issues. Q8 (S6 `bob_lang` unused) is editorial; S6 runs and tests the correct behavior regardless of how the column is resolved.

- **Prerequisites not yet met:**
  - N02 (native Android app) is `blocked` until an Android emulator or device is available (`adb` and `emulator` not on PATH per E01). Cross-client headless testing (A02) is not blocked.
  - K1.1 specifies JDK 17; JDK 22 is installed. Compatible; update K1.1 in a separate spec task if a strict bound is needed.
  - Platform commands in `platform/ios.md` section 9 and `platform/android.md` section 9 are marked unverified; they become verifiable once E01-level tools are used to build and run.

- **Generation may start for:**
  - iOS client (A01): all shared rules and all iOS rules are fully specified and unambiguous.
  - Android client (A02): all shared rules and all Android rules are fully specified. JDK 22 is compatible with Gradle 8.x.
  - Server (B01): all server-enforced rules (A3.2–A3.7, P6.1–P6.6) are complete.
  - Cross-client scenarios S1–S6 are all implementable; no scenario is blocked.

- **Generation must wait for:**
  - N02 native app build and launch require a working Android emulator or device.
  - MT1, MT3, MT4 coverage extensions (display-only; may be addressed during N01/N02).
