# Evidence ledger

Records of checks actually run in this generation run. Task definitions and statuses are in `.agent/TASKS.md`; procedures in `.agent/WORKFLOW.md`.

## Run

- Run ID:
- Started:
- Repository commit at start:
- Spec revision:
- Agent tool and version:
- Machine and OS:

## Rules

- Add an entry only for a check that was actually executed in this run. Never copy entries from an earlier run.
- Every entry has all fields below. A field that cannot be filled is written as `unknown`, never guessed.
- A check that was not executed is not recorded here; mark it NOT RUN in the task's handoff instead.
- Entries are append-only. To correct one, add a new entry that references it; never edit or delete the original.
- A task in `.agent/TASKS.md` may be marked `done` only when its entries here cover all of its completion criteria.

## Entry format

```
### E-<task ID>-<short name>

- Task:
- Role and tool:
- Working directory:
- Command:
- Exit status:
- Result: PASS / FAIL, with counts
```

## Entries

None yet.