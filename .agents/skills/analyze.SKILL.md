---
name: analyze
description: Analyze the Spec_drive specification for affected rules, gaps, and acceptance scenarios, and write a task plan before client generation or after a spec change.
---

# Skill: Specification Analyzer

Invoked as `/analyze` in Claude Code. Runs the Specification Analyzer role defined in `AGENTS.md`.

## What this skill does

Reads the spec, identifies all rules affected by the current task or change, flags gaps, and writes a plan to `.agents/TASKS.md`. It writes no code. Its output is the plan that unblocks the two Implementer skills.

## When to run this

- Before any generation or regeneration (`WORKFLOW.md` W2, step 3).
- After any spec change (`WORKFLOW.md` W1).
- Whenever the spec seems ambiguous or the implementers hit a contradiction.

## Instructions

You are acting as the Specification Analyzer. Follow `AGENTS.md` - Specification Analyzer role - exactly.

### Step 1 - identify scope

Read the task or change request. If none was given, analyze the full spec for the first generation.

List every spec file that bears on the task:
- `spec/domain.md` - entities, value rules, statuses
- `spec/protocol.md` - event envelope, idempotency, ordering
- `spec/api.md` - wire format, endpoints, error codes
- `spec/offline-behavior.md` - outbox, sync, lifecycle
- `spec/ui.md` - screens and display
- `spec/test.md` - headless runner contract, scenarios, fixtures
- `spec/platform/ios.md` - Swift-specific choices
- `spec/platform/android.md` - Kotlin-specific choices

### Step 2 - extract affected rules

For each file you read, list every rule ID (`D…`, `P…`, `A…`, `O…`, `U…`, `T…`, `I…`, `K…`) that is affected by the task or that bears on the behavior being implemented.

Classify each rule:
- **shared** - both clients must implement it identically
- **iOS only** - `I…` rules or Swift-specific pitfalls
- **Android only** - `K…` rules or Kotlin-specific pitfalls
- **server** - server must enforce it

### Step 3 - find spec gaps

For each affected rule, ask:
1. Is the rule complete enough to implement without guessing?
2. Does any other rule contradict it?
3. Is there a test scenario or fixture in `spec/test.md` that would fail if this rule were broken?

List every gap, contradiction, or missing test. Mark each as:
- `[BLOCKER]` - generation must not proceed until resolved
- `[QUESTION]` - ambiguous but a reasonable default exists; state the default you'd assume
- `[MISSING TEST]` - behavior is specified but not tested

### Step 4 - write the analysis report

Fill in `.agents/analysis/SPEC01.md` (it is a template; populate every section):
- **Run block**: today's date, current `git rev-parse HEAD`, spec revision, tool and version, scope of the request.
- **Affected rules**: list every rule ID classified as shared, iOS-only, Android-only, or server.
- **Questions**: one entry per gap or contradiction using the `Q<n>` format already in the template.
- **Acceptance coverage**: list scenarios that must pass, client-only checks, and coverage gaps.
- **Conclusion**: unresolved behavioral questions, prerequisites not yet met, what generation may start, what must wait.

Do not leave any section as "None yet" if the analysis found relevant content for it.

### Step 5 - update the task register

Update the relevant task entry in `.agents/TASKS.md`:
- Affected rule IDs
- Which platforms are affected
- Open questions (from step 3) that are `[BLOCKER]`
- The acceptance scenarios from `spec/test.md` that must pass
- Any assumptions you are making for `[QUESTION]` items

### Step 6 - record evidence

Append one entry to `.agents/evidence/LEDGER.md` using the template format in that file:
- **ID**: `E-SPEC01-analysis`
- **Task**: SPEC01
- **Role and tool**: Specification Analyzer / analyze skill
- **Working directory**: repository root
- **Command**: `/analyze` (or describe the invocation)
- **Exit status**: 0 if the report was written without tool errors
- **Result**: PASS with a one-line summary (e.g. "Report written; N rules classified; N blockers"), or FAIL with the reason

### Step 7 - handoff

End with:
- Role: Specification Analyzer
- What changed: list of files read and plan written
- Rules covered: by ID
- Blockers: any `[BLOCKER]` items (stop generation until resolved)
- Assumptions: any `[QUESTION]` items and the assumed defaults
