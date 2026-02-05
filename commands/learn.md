# /learn - Extract Reusable Patterns

**Model:** opus (requires judgment)

Run after solving a non-trivial problem.

## What to Extract

✓ Error resolution (root cause + fix), debugging techniques, workarounds (library quirks, API limitations), project conventions

✗ Trivial fixes, one-time issues, obvious patterns

## Process

1. Review session for most valuable pattern
2. Draft skill file
3. Ask user for category (e.g., `python`, `git`, `debugging`)
4. Save to:
   - **claude-foundry**: `<config_repo>/skills/learned/<category>/<name>.md` (default, shared)
   - **project-local**: `.claude/skills/learned-local/<category>/<name>.md` (optional)
5. Confirm content, save, create dirs if needed

## Skill Format

```markdown
# [Pattern Name]

**Extracted:** [Date]
**Context:** [When this applies]

## Problem
[What this solves]

## Solution
[The pattern/technique]

## Example
[Code if applicable]

## When to Use
[Trigger conditions]
```

After saving: remind to commit/push claude-foundry repo, run `setup.py init` to deploy.
