@AGENTS.md

## Claude-specific notes

### Before editing
Read the task entry in `.agents/task.md`, the `spec/` sections it references, and the relevant
`.agents/design.md` section. Then read the platform file for each folder you touch —
`backend/AGENTS.md`, `ios/AGENTS.md`, or `android/AGENTS.md` — before making any edits. These
are not loaded automatically; open them explicitly.

### Verification honesty
- A headless pass does not prove a native build or lifecycle correctness. State which one you ran.
- Mark a task complete in `.agents/task.md` only when its acceptance evidence (command + exit
  status) exists in this session.
