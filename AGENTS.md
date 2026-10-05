# AGENTS.md

Shared instructions for every coding agent in this repository (Claude Code, Codex, and any delegated agent). This file is self-sufficient: an agent that reads only this file must still follow the rules. Paths are relative to the repository root.

## Project

A spec-driven code generator. The specification in `spec/` is turned into two independent clients, Swift (iOS) and Kotlin (Android), that must behave identically against one small server. The generated client code is disposable: deleting it and regenerating from `spec/` must produce working clients again.

## Source of truth

Behavioral requirements are defined only in `spec/`:

- `product.md`: what the product does and why
- `domain.md`: entities, usernames, text rules, statuses (`D…` rules)
- `protocol.md`: events, submission, sequencing, cursors, extension (`P…` rules)
- `api.md`: endpoints and wire format
- `offline-behavior.md`: outbox, sync cycle, retries, lifecycle (`O…` rules)
- `ui.md`: screens and display
- `test.md`: runner contract, scenarios, fixtures (`T…` rules)
- `platform/ios.md`, `platform/android.md`: platform choices and commands

If the spec and implementation disagree, the spec wins. If two spec files disagree, or the spec is ambiguous or silent on a behavior, stop work on that behavior and report the files, the conflicting rules, and a proposed resolution. Never choose one silently.

## Generation boundary

Generated paths: `clients/ios/` and `clients/android/`. Everything else, `spec/`, `server/`, `harness/`, `.agents/skills/`, `generator/`, `.agents/`, instruction files, `DESIGN.md`, `README.md`, is hand-maintained and MUST NOT be deleted or overwritten by generation.

When generating or regenerating client code:

- Use only `spec/` and declared generator inputs. Never read, copy, or diff against previously generated client code, build output, or the git history of generated paths.
- Implement every applicable rule and add no behavior the spec does not define. Details the spec leaves open (layout, naming, internal structure) are free choices; list significant ones in the handoff.
- Cite the rule a piece of logic implements in a short comment (`// P7.4`).

## Roles

Work is split into four roles. A role is a set of responsibilities and permissions, not a separate program. One agent may perform several roles in sequence, but must follow each role's rules while in it and say which role it is acting in. Roles run in this order: Analyzer, then the two Implementers (in either order or in parallel), then Verifier.

### Specification Analyzer

- Reads `spec/` and identifies the rules affected by the requested change, by ID.
- Classifies each rule as shared (both clients) or platform-specific.
- Finds gaps, contradictions, and ambiguities in the spec and reports them before any implementation starts.
- Writes the plan as a task entry in `.agents/TASKS.md`: affected rules, affected platforms, open questions, and the acceptance scenarios from `spec/test.md` that must pass.
- **Writes:** `.agents/TASKS.md` only. Never writes code, never edits `spec/`.

### iOS Implementer

- Implements the planned rules in Swift: domain, protocol, persistence, sync, UI, headless runner, and unit tests, following `spec/platform/ios.md`.
- **Writes:** the iOS generated paths only.
- **Must not read** the Android generated code. The client must be derived from the spec, not translated from Kotlin.

### Android Implementer

- Implements the planned rules in Kotlin: domain, protocol, persistence, sync, UI, headless runner, and unit tests, following `spec/platform/android.md`.
- **Writes:** the Android generated paths only.
- **Must not read** the iOS generated code. The client must be derived from the spec, not translated from Swift.

### Verifier

- Builds both clients and runs their unit tests.
- Runs every scenario in `spec/test.md` with real clients against the real server, in both role assignments (Swift as Alice, then Kotlin as Alice).
- Compares results to the spec, and reports each violation with the rule ID, the scenario, the expected result, and the observed result.
- **Writes:** test reports and evidence only. Never edits client code, the server, `spec/`, or test expectations. A failure goes back to the responsible implementer, or to the Analyzer if the spec is at fault.

## Commands

Run only commands documented in `spec/platform/*.md` or the generator's documentation. If a command is not documented, report the check as NOT RUN; never invent one. A missing toolchain (Xcode, Android SDK) means NOT RUN, never PASS. A headless pass does not prove the native app works.

## Rules

- Never modify `spec/` to make code or tests pass. A spec change is a separate, explicit task that starts with the Analyzer.
- Never weaken a test expectation to match an implementation.
- Commit in small, coherent steps whose messages say what changed and why. Never squash work into one final commit or rewrite history.
- Keep attribution honest: record which files were generated, which were hand-written, and by which role.

## Handoff

Every role ends with: role, what changed, rules covered (by ID), each check as PASS / FAIL / NOT RUN with command and exit status, assumptions, and open spec gaps.