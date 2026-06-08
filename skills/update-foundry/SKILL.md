---
name: update-foundry
description: Update Claude Foundry configuration (DEPRECATED — offers migration to agent-foundry)
disable-model-invocation: true
allowed-tools: Bash(bash *)
---

# /update-foundry — Update / Migrate Foundry Configuration

> **claude-foundry is DEPRECATED.** It has been superseded by
> **[agent-foundry](https://github.com/poelsen/agent-foundry)** — a multi-CLI
> foundry that supports Claude Code *and* GitHub Copilot CLI (plus the
> `AGENTS.md` ecosystem). Skills, rules, and MCP now deploy per-CLI.

## What to do when this command is invoked

**First, tell the user claude-foundry is deprecated** and that agent-foundry is
the successor. Then offer two choices:

1. **Migrate to agent-foundry (recommended, one-way):** repoints this project to
   `poelsen/agent-foundry` and re-initialises it on the new layout. Run:
   ```bash
   bash .claude/skills/update-foundry/scripts/update-foundry.sh --switch $ARGUMENTS
   ```
2. **Take a final claude-foundry update** (stay on the deprecated repo for now):
   ```bash
   bash .claude/skills/update-foundry/scripts/update-foundry.sh $ARGUMENTS
   ```

Do not pick for the user — ask which they want, unless they already said
"switch"/"migrate" (use option 1) or explicitly asked to stay (option 2). If
`$ARGUMENTS` already contains `--switch`, run option 1 directly.

## After running

Show the script output to the user verbatim. After a successful run:
- Command changes take effect immediately
- Rule changes take effect next interaction
- Agent/skill changes load on demand

After a **migration**, all future `/update-foundry` runs pull from
agent-foundry automatically (the manifest's `repo_url` was repointed). If the
script fails, help the user troubleshoot from the error output.

## Related commands

- `/update-foundry-check` — check for updates only (no changes)
- `/update-foundry-interactive` — full interactive reconfigure menu
