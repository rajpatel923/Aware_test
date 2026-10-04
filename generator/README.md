# Generator

This directory documents how the spec is turned into client code. The actual prompts are in `skills/`; the slash commands that invoke them are in `.claude/commands/`.

## How it works

Each generation role maps to one Claude Code slash command:

| Slash command | Skill file | Role |
|---|---|---|
| `/analyze` | `skills/analyze.md` | Reads spec, finds gaps, writes plan |
| `/generate-ios` | `skills/generate-ios.md` | Generates `clients/ios/` |
| `/generate-android` | `skills/generate-android.md` | Generates `clients/android/` |
| `/verify` | `skills/verify.md` | Builds, runs scenarios, records results |

When you type `/generate-ios` in Claude Code, it loads `skills/generate-ios.md` as the agent's instructions. The agent reads only `spec/`, writes only `clients/ios/`, and cites the rule ID on every piece of behavior logic.

## To regenerate (full run)

**Prerequisites:** macOS with Xcode, JDK 17, Android SDK, Python 3.11+, Claude Code CLI.

**1. Delete generated output:**
```bash
rm -rf clients/ios clients/android
```

**2. Open Claude Code at the repo root.** CLAUDE.md and AGENTS.md are loaded automatically.

**3. Run the Analyzer (optional if spec hasn't changed):**
```
/analyze
```
If the output shows `[BLOCKER]` items, fix them in `spec/` before continuing.

**4. Run both Implementers.**

Option A — sequential (one terminal):
```
/generate-ios
/generate-android
```

Option B — parallel (two terminals, faster):
```bash
# Terminal 1                    # Terminal 2
claude                          claude
/generate-ios                   /generate-android
```
The two implementations must not read each other's output. Opening separate sessions enforces this automatically.

**5. Run the Verifier:**
```
/verify
```

## Why this structure

- `skills/` files are the authoritative prompt templates. They are hand-written and reviewed.
- `.claude/commands/` files are one-liners that load the skill and invoke the role. They are the execution interface.
- Separating them means you can improve a skill without touching the command file, and the README stays the single source of truth for invocation.

## Adding a new feature (evolution path)

1. Register the new event type in `spec/protocol.md` (P3.8), add its body in `spec/domain.md`, display in `spec/ui.md`, and scenarios in `spec/test.md`.
2. Delete `clients/ios/` and `clients/android/`.
3. Run steps 2–5 above with no changes to the generator.
4. If the regeneration needed a generator change (a skill needed updating), record why in `DESIGN.md` section 9.
