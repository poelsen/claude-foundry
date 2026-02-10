---
name: update-foundry
description: Update Claude Foundry configuration to latest release
disable-model-invocation: true
allowed-tools: Bash(bash *)
---

# /update-foundry - Update Claude Foundry Configuration

## Usage

- `/update-foundry` — Check and apply update
- `/update-foundry --check` — Check only
- `/update-foundry --interactive` — Full interactive menu

## Instructions

Run the update script, passing through user arguments:

```bash
bash .claude/skills/update-foundry/scripts/update-foundry.sh $ARGUMENTS
```

Show the output to the user verbatim. After a successful update:
- Command changes take effect immediately
- Rule changes take effect next interaction
- Agent changes load on demand

If the script fails, help the user troubleshoot based on the error output.
