# /learn - Extract Reusable Patterns

Analyze the current session and extract patterns worth saving as learned skills.

## Trigger

Run `/learn` after solving a non-trivial problem.

## What to Extract

1. **Error Resolution** — root cause + fix for reusable errors
2. **Debugging Techniques** — non-obvious diagnostic steps
3. **Workarounds** — library quirks, API limitations, version-specific fixes
4. **Project Conventions** — codebase patterns, architecture decisions

## What NOT to Extract

- Trivial fixes (typos, simple syntax errors)
- One-time issues (specific API outages)
- Obvious patterns (standard library usage)

## Process

1. Review session for the most valuable extractable pattern
2. Draft the skill file (see format below)
3. **Ask user to pick a category** — suggest based on context (e.g., `python`, `git`, `debugging`, `pyside6`). User can pick an existing category or create a new one.
4. **Save locations** (not mutually exclusive):
   - **claude-foundry repo** (always selected by default): Save to `<config_repo>/skills/learned/<category>/<skill-name>.md`. The `config_repo` path is in `.claude/setup-manifest.json` under the `config_repo` key. If not found, ask user for the path.
   - **Project-local** (ask user): Save to `<project>/.claude/skills/learned-local/<category>/<skill-name>.md`. Use this for patterns specific to this codebase.
5. Ask user to confirm content before saving
6. Save to chosen locations. Create directories if needed.

## Skill File Format

Save as `<category>/<kebab-case-name>.md`:

```markdown
# [Descriptive Pattern Name]

**Extracted:** [Date]
**Context:** [When this applies]

## Problem
[What problem this solves]

## Solution
[The pattern/technique/workaround]

## Example
[Code example if applicable]

## When to Use
[Trigger conditions]
```

## After Saving

- Remind user to commit and push claude-foundry repo if saved there
- Remind user to run `setup.py init` or `update-all` to deploy to projects
