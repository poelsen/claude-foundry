# /snapshot - Session Context Snapshots

**Model:** opus for capture/restore (judgment), haiku for --list (mechanical)

## Usage

- `/snapshot` — Capture current session
- `/snapshot --restore` — Resume from most recent
- `/snapshot --list` — Show all snapshots

## Capture (default)

Extract from session: active task, key decisions, files modified, open questions, next steps, user preferences.

Write to `.claude/snapshots/YYYY-MM-DD-HHMM-<short-desc>.md`:

```markdown
---
created: YYYY-MM-DDTHH:MM:SSZ
goal: "One-line objective"
status: in_progress | completed | blocked
---

## Active Task
[Current focus]

## Decisions Made
- [Decision and why]

## Files Modified
- path/file.py — what changed

## Open Questions
- [Unresolved items]

## Next Steps
- [ ] Next action
```

Guidelines: ~5KB max, summarize don't transcribe, use `file:line` refs not code snippets, max 5 decisions / 10 files / 5 questions. Keep 10 most recent, prune older.

## Restore (`--restore`)

Read most recent snapshot, present contents. If auto-generated with `trigger:` frontmatter, also read referenced transcript. Ask user which threads to continue.

## List (`--list`)

Show all snapshots: filename, date, goal, status.
