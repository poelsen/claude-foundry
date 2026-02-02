# /snapshot - Session Context Snapshots

Capture, restore, or list session context snapshots for recovery after compaction or restart.

## Usage

- `/snapshot` — Capture current session state (default)
- `/snapshot --restore` — Resume from most recent snapshot
- `/snapshot --list` — Show all snapshots

## Capture Mode (default)

1. **Analyze the current session** and extract:
   - Active task / goal (what are we working on?)
   - Key decisions made and their reasoning
   - Files modified and why
   - Open questions or unresolved issues
   - Next steps (immediate actions remaining)
   - User preferences or constraints mentioned

2. **Generate a short description** (2-4 words, kebab-case) for the filename.

3. **Write snapshot** to `.claude/snapshots/YYYY-MM-DD-HHMM-<short-desc>.md` using this format:

```markdown
---
created: YYYY-MM-DDTHH:MM:SSZ
goal: "One-line session objective"
status: in_progress | completed | blocked
---

## Active Task
[Current focus — what were we working on?]

## Decisions Made
- [Key decision and why]

## Files Modified
- path/to/file.py — what changed and why

## Open Questions
- [What's still unclear or unresolved?]

## Next Steps
- [ ] Immediate next action
- [ ] Follow-up task

## User Preferences
[Session-specific constraints or preferences]
```

4. **Create `.claude/snapshots/`** directory if it doesn't exist.

5. **Prune old snapshots** — keep only the 10 most recent `.md` files, delete the rest.

6. **Report** the snapshot filename and a one-line summary.

### Guidelines

- Target ~5KB — be concise but capture what matters
- Summarize decisions, don't transcribe conversations
- Use relative file paths
- Reference `file:line` for specific code locations, don't include code snippets
- Max 5 decisions, 10 files, 5 open questions

## Restore Mode (`--restore`)

1. **List snapshots** in `.claude/snapshots/` sorted by filename (newest first).
2. If none exist: "No snapshots found. Use `/snapshot` to create one."
3. **Read the most recent snapshot** and present its contents.
4. If the snapshot was auto-generated (has `trigger:` in frontmatter and references a transcript), **read the transcript** and summarize the session context from it.
5. **Ask the user** which threads to continue or if they want to restore a different snapshot.

## List Mode (`--list`)

1. **List all snapshots** in `.claude/snapshots/` sorted by filename (newest first).
2. For each, show: filename, created date, goal, status.
3. If none exist: "No snapshots found."
