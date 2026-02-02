# Claude Config Project

This repo contains my Claude Code configuration - rules, agents, skills, hooks, and commands.

## Project Context
- Use `tools/setup.py init` to deploy config to projects
- Edits here take effect after re-running `setup.py init` or `update-all`
- Push changes to sync across machines

## Structure
- `rules/` - Base rules (globally loaded for all projects)
- `rule-library/` - Modular rules (copied/symlinked per-project)
- `agents/` - Custom agent definitions
- `commands/` - Slash commands
- `skills/` - Custom skills
- `skills/learned/` - Learned patterns (deployed to projects by category)
- `hooks/` - Pre/post tool hooks
- `mcp-configs/` - MCP server configurations

## Commands

| Command | Purpose |
|---------|---------|
| `/update-codemaps` | Generate or refresh architecture codemaps |
| `/learn` | Extract reusable patterns from current session |
| `/recall` | Search and surface learned skills |
| `/snapshot` | Capture/restore session context snapshots |

## Modular Rules
- rule-library/platform/github.md

## Common Tasks
- Edit rules in `rules/` or `rule-library/`
- Test changes by re-running `tools/setup.py init`
- Commit and push to sync across machines
