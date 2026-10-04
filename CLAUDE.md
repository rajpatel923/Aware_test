# Repository Instructions

This repository is a spec-driven code generator. The specification in `spec/` is turned into two independent clients (Swift and Kotlin) that must behave identically against one server. Paths below are relative to the repository root.

## Source of truth

Behavioral requirements are defined only in `spec/`:

- `product.md`: what the product does and why
- `domain.md`: entities, usernames, text rules, statuses (`D…` rules)
- `protocol.md`: events, submission, sequencing, cursors, extension (`P…` rules)
- `api.md`: endpoints and wire format
- `offline-behavior.md`: outbox, sync cycle, retries, lifecycle (`O…` rules)
- `ui.md`: screens and display
- `test.md`: runner contract, scenarios, fixtures (`T…` rules)
- `platform/ios.md`, `platform/android.md`: platform-specific choices and commands

If the spec and implementation disagree, the spec wins. If two spec files disagree, or the spec is ambiguous or silent on a behavior, stop work on that behavior and report the files, the conflicting rules, and a proposed resolution. Do not choose one silently.

## Generation boundary

Generated paths: `clients/ios/` and `clients/android/`. Everything else is hand-maintained and MUST NOT be modified during generation.

When generating or regenerating client code:

- Use only `spec/` and the declared generator inputs as sources. Never read, copy, or diff against previously generated client code, build output, or git history of generated paths.
- Write only inside the generated paths. Never modify `spec/`, the server, the test harness, or instruction files.
- Implement every applicable rule; add no behavior the spec does not define. Implementation details the spec leaves open (layout, naming, internal structure) are free choices; list significant ones in the handoff.
- Cite the rule a piece of logic implements in a short comment (`// P7.4`), so behavior can be traced back to the spec.

## Workflow

1. Read the relevant spec files and identify the affected rules (by ID).
2. Identify the affected platforms. Read `spec/platform/<platform>.md` for each.
3. Implement or generate within the boundary.
4. Run the platform tests, then the cross-client scenarios in `spec/test.md` (both role assignments).
5. Record each check as PASS, FAIL, or NOT RUN, with the exact command and exit status.

Run only commands documented in `spec/platform/*.md` or the generator's own documentation. If a command is not documented, report the check as NOT RUN; never invent one. A missing toolchain (Xcode, Android SDK) also means NOT RUN, never PASS. A headless pass does not prove the native app works.

## Rules

- Never modify the spec to make code or tests pass. A spec change is a separate, explicit task.
- Never weaken a test expectation in `spec/test.md` to match an implementation.
- Commit in small, coherent steps with messages that say what changed and why. Never squash work into one final commit or rewrite history.
- Keep attribution honest: say which files you generated and which you edited by hand.

## Handoff

End every task with: what changed, which rules it implements, each check as PASS / FAIL / NOT RUN, assumptions made, and open spec gaps.