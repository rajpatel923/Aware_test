# SPEC01 — Specification analysis

Written by the Specification Analyzer (`AGENTS.md`) before generation. This report is not a generator input and defines no behavior: only `spec/` does. Task status lives in `.agent/TASKS.md`; check results in `.agent/EVIDENCE.md`.

## Run

- Date:
- Repository commit:
- Spec revision:
- Agent tool and version:
- Requested change or scope:

## Rules

- List only rules affected by the requested scope, by ID. Do not list every rule in the spec.
- A gap the analyzer fills with an assumption is a **question**, not a resolution. Record the proposed default and mark it unapproved.
- A question that changes shared behavior blocks generation of that behavior until it is resolved through the spec-change workflow (`.agent/WORKFLOW.md` W1).
- A question that is only a free implementation choice may proceed; say so explicitly.
- Never report "no blockers" while any question is unresolved.

## Affected rules

**Shared (both clients):**

**iOS only:**

**Android only:**

**Server (hand-written; clients must handle its responses):**

## Questions

Use one entry per question.

```
### Q<n>. <short title>

- Rules involved:
- Gap or contradiction:
- Proposed default (unapproved):
- Kind: behavioral decision / free implementation choice / toolchain prerequisite / editorial
- Blocks:
- Owner document for the fix:
```

None yet.

## Acceptance coverage

**Scenarios that must pass** (from `spec/test.md` section 5):

**Client-only checks** (from `spec/test.md` section 7):

**Coverage gaps** (rules in scope with no scenario, fixture, or client-only check):

## Conclusion

- Unresolved behavioral questions:
- Prerequisites not yet met:
- Generation may start for:
- Generation must wait for: