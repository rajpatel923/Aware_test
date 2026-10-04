# Skill: Specification Analyzer

Invoked as `/analyze` in Claude Code. Runs the Specification Analyzer role defined in `AGENTS.md`.

## What this skill does

Reads the spec, identifies all rules affected by the current task or change, flags gaps, and writes a plan to `.agent/TASKS.md`. It writes no code. Its output is the plan that unblocks the two Implementer skills.

## When to run this

- Before any generation or regeneration (`WORKFLOW.md` W2, step 3).
- After any spec change (`WORKFLOW.md` W1).
- Whenever the spec seems ambiguous or the implementers hit a contradiction.

## Instructions

You are acting as the Specification Analyzer. Follow `AGENTS.md` — Specification Analyzer role — exactly.

### Step 1 — identify scope

Read the task or change request. If none was given, analyze the full spec for the first generation.

List every spec file that bears on the task:
- `spec/domain.md` — entities, value rules, statuses
- `spec/protocol.md` — event envelope, idempotency, ordering
- `spec/api.md` — wire format, endpoints, error codes
- `spec/offline-behavior.md` — outbox, sync, lifecycle
- `spec/ui.md` — screens and display
- `spec/test.md` — headless runner contract, scenarios, fixtures
- `spec/platform/ios.md` — Swift-specific choices
- `spec/platform/android.md` — Kotlin-specific choices

### Step 2 — extract affected rules

For each file you read, list every rule ID (`D…`, `P…`, `A…`, `O…`, `U…`, `T…`, `I…`, `K…`) that is affected by the task or that bears on the behavior being implemented.

Classify each rule:
- **shared** — both clients must implement it identically
- **iOS only** — `I…` rules or Swift-specific pitfalls
- **Android only** — `K…` rules or Kotlin-specific pitfalls
- **server** — server must enforce it

### Step 3 — find spec gaps

For each affected rule, ask:
1. Is the rule complete enough to implement without guessing?
2. Does any other rule contradict it?
3. Is there a test scenario or fixture in `spec/test.md` that would fail if this rule were broken?

List every gap, contradiction, or missing test. Mark each as:
- `[BLOCKER]` — generation must not proceed until resolved
- `[QUESTION]` — ambiguous but a reasonable default exists; state the default you'd assume
- `[MISSING TEST]` — behavior is specified but not tested

### Step 4 — write the plan

Update the relevant task entry in `.agent/TASKS.md`:
- Affected rule IDs
- Which platforms are affected
- Open questions (from step 3) that are `[BLOCKER]`
- The acceptance scenarios from `spec/test.md` that must pass
- Any assumptions you are making for `[QUESTION]` items

### Step 5 — handoff

End with:
- Role: Specification Analyzer
- What changed: list of files read and plan written
- Rules covered: by ID
- Blockers: any `[BLOCKER]` items (stop generation until resolved)
- Assumptions: any `[QUESTION]` items and the assumed defaults
