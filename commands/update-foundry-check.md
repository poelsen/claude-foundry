# /update-foundry-check - Check for Foundry Updates

> **Note:** claude-foundry is deprecated in favour of
> [agent-foundry](https://github.com/poelsen/agent-foundry). To migrate, run
> `/update-foundry` and choose to switch (or `/update-foundry --switch`).

Check if a newer version of claude-foundry is available without applying changes.

Read and follow the full skill instructions in `.claude/skills/update-foundry/SKILL.md`, but run with the `--check` flag:

```bash
bash .claude/skills/update-foundry/scripts/update-foundry.sh --check
```

Show the output to the user verbatim.
