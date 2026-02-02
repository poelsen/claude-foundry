# Claude Code Configuration

Complete Claude Code configuration with modular rules, agents, skills, hooks, and commands.

## Structure

```
claude_config/
├── .github/workflows/        # CI/CD (CalVer release on merge)
├── rules/                    # Base rules (globally loaded)
├── rule-library/             # Modular rules (pick per-project)
│   ├── lang/                 # python, c, cpp, rust, go, react, etc.
│   ├── domain/               # embedded, dsp-audio, gui
│   ├── security/             # sandbox, internal, enterprise
│   ├── style/                # backend, scripts, library
│   ├── arch/                 # rest-api, react-app, monolith
│   └── platform/             # github
├── agents/                   # Custom agent definitions
├── commands/                 # Slash commands (/snapshot, /learn, /update-codemaps)
├── hooks/                    # Global hooks + per-project hook library
├── mcp-configs/              # MCP server configurations
├── skills/                   # Custom skills
├── tools/                    # Setup tooling (setup.py)
└── VERSION                   # CalVer version (YYYY.MM.DD[.N])
```

## Setup

Requires Python 3.11+. No dependencies beyond stdlib.

```bash
# Initialize a project (interactive — detects languages, suggests rules/hooks/agents)
python3 tools/setup.py init [project_dir]

# Re-apply saved config to all known projects
python3 tools/setup.py update-all

# Check for updates against remote
python3 tools/setup.py check

# Show current version
python3 tools/setup.py version
```

`init` copies selected rules, agents, skills, hooks, and plugins into the target project's `.claude/` directory. Selections are saved to `.claude/setup-manifest.json` so `update-all` can re-apply non-interactively.

## Global Commands

These commands are available in any project using this config:

| Command | Purpose |
|---------|---------|
| `/snapshot` | Capture/restore session context snapshots |
| `/learn` | Extract reusable patterns from current session |
| `/update-codemaps` | Generate or refresh architecture codemaps |

## Global Hooks

Defined in `hooks/hooks.json`, active in all sessions:

- **Dev server blocker** — blocks dev servers outside tmux
- **tmux reminder** — suggests tmux for long-running commands
- **git push pause** — pauses before push for review
- **doc blocker** — blocks creation of unnecessary .md files
- **PR creation logger** — logs PR URL after `gh pr create`
- **JSON validator** — validates JSON after editing .json files
- **Auto-snapshot** — captures session context before compaction and on exit

Per-project hooks (formatters, type checkers) are in `hooks/library/` — see `hooks/library/README.md`.

## Versioning

CalVer format: `YYYY.MM.DD` with `.N` patch suffix for same-day releases.

Version is bumped automatically by GitHub Actions on merge to `master`. The workflow updates `VERSION` and creates a git tag.

## Out of Scope

This config handles Claude Code behavior — how the agent works, reviews, plans, and interacts. It does **not** replace project-level tooling:

- **Linting / debug statement detection** — use CI/CD (e.g., pre-commit hooks, GitHub Actions)
- **Formatting** — per-project concern; see `hooks/library/` for opt-in formatter hooks
- **Type checking** — per-project concern; see `hooks/library/` for opt-in type checker hooks
- **Language-specific build steps** — configure in project CI, not here

## Not Tracked (local/sensitive)

These stay in `~/.claude/` and are NOT in this repo:
- `.credentials.json` - OAuth credentials
- `settings.json` - Local settings
- `cache/`, `debug/`, `downloads/` - Local data
- `history.jsonl` - Command history
- `projects/`, `plans/`, `todos/` - Local state
- `telemetry/`, `statsig/` - Analytics
