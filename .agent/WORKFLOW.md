# Workflow

How work moves through this repository, step by step. `AGENTS.md` defines the roles and their permissions; 
`.agent/TASKS.md` holds the task list and evidence; 
`spec/` defines behavior.

Every workflow below ends with a handoff (`AGENTS.md`) and a commit. Never batch several workflows into one commit.

## W1. Change the spec

Use for any new or changed requirement, including fixes to spec bugs found during generation.

1. **Analyzer:** state the change in one sentence and list the affected rule IDs, or the new IDs to be added.
2. **Analyzer:** find every spec file that mentions the topic. Each topic has one owning file (see `DESIGN.md` for the ownership table); change the owner, and update other files only where they cite it.
3. Edit the spec. New rules get the next free ID in their file; existing IDs are never renumbered or reused.
4. Update `spec/test.md`: every new or changed rule needs a scenario, fixture, or client-only check that would fail if the rule were broken.
5. **Analyzer:** reread all touched files for contradictions. Any rule marked [DECISION NEEDED] blocks generation of the behavior it covers.
6. Commit the spec change alone: `spec: <what changed> (<rule IDs>)`.
7. Add or reopen tasks in `.agent/TASKS.md` for regeneration and verification (W2, W3).

## W2. Generate or regenerate a client

Use to produce client code from the spec, for a first generation, after a spec change, or to prove regeneration.

1. Confirm the inputs exist: `spec/`, the platform file (`spec/platform/ios.md` or `spec/platform/android.md`), and the generator (`skills/`). If any is missing, stop and record the task as `blocked`.
2. Confirm no open [DECISION NEEDED] covers behavior being generated.
3. **Analyzer:** write the plan into the task entry: affected rules, platforms, and the scenarios that must pass.
4. Run the generator for one platform using its documented command.
5. The implementer runs its own build and unit tests and fixes failures inside its generated paths.
6. If the implementer finds the spec ambiguous or wrong, it stops that behavior and reports it. The fix goes through W1, never into generated code alone.
7. Commit the generated output alone: `gen(<platform>): <scope> from spec <revision>`. The message states it is generated.
8. Repeat for the other platform, then run W3.

**Generated code is never edited by hand.** If generated code is wrong, fix the spec (W1) or the generator (W5) and regenerate. A hand edit would be lost at the next regeneration and would make the boundary a lie.

## W3. Verify

Use after any generation, server change, or harness change.

1. **Verifier:** start a fresh server.
2. Build both clients and run their unit tests.
3. Run every scenario in `spec/test.md` in both role assignments.
4. Record each check in the task's evidence: PASS, FAIL, or NOT RUN, with command, working directory, exit status, and log location.
5. For each failure, identify the rule ID and route it:
    - The client violates a clear rule: back to that platform's implementer through W2.
    - The spec is ambiguous, contradictory, or wrong: to the Analyzer through W1.
    - The server or harness is wrong: fix it through W4.
6. The Verifier never edits code, spec, or tests to make a check pass.
7. Commit evidence and task updates: `verify: <scope> <pass count>/<total>`.

## W4. Change hand-written components

Use for the server, the test harness, and the generator's own code.

1. Confirm the change does not alter behavior the spec defines. If it does, run W1 first.
2. Make the change and run that component's own tests.
3. Run W3, because the server and harness are what the clients are judged against.
4. Commit: `server: …`, `harness: …`, or `generator: …`.

## W5. Change the generator

Use when generation is unreliable: missing behavior, broken builds, or agents ignoring rules.

1. Record the failure with an example: the spec rule, what was generated, and what was expected.
2. Decide where the fix belongs. If the rule is unclear, fix the spec (W1). If the agent had the right information but used it badly, fix the generator's prompts, skills, or steps.
3. Never fix a generator problem by adding behavior to a prompt that is not in the spec. Prompts may explain how to implement; only the spec says what.
4. Regenerate the affected platform (W2) and verify (W3).
5. Commit: `generator: <what changed and why>`.

## W6. Add a feature (evolution)

1. Run W1: register the event type in `protocol.md`, define its body in `domain.md`, its display in `ui.md`, and its scenarios in `test.md`.
2. Run W2 for both platforms with no generator changes.
3. Run W3.
4. If regeneration needed a generator change, record why in `DESIGN.md`: that is a limit of the harness's genericity.

## Commit conventions

- One workflow step's output per commit; never a single final commit.
- Prefix by area: `spec:`, `gen(ios):`, `gen(android):`, `server:`, `harness:`, `generator:`, `verify:`, `docs:`, `chore:`.
- State attribution when it is not obvious: commits of generated code say so; hand-written commits are by the author.
- Never rewrite or squash history.