# Claude Foundry

> **Early alpha.** This project is under active development. The current rule set focuses on **Python** and **PySide6/Qt** projects — other languages have base rules but are less battle-tested. Expect breaking changes.

A foundry for casting [Claude Code](https://docs.anthropic.com/en/docs/claude-code) configurations across project types and languages. Provides modular rules, agents, skills, hooks, and slash commands that shape how Claude Code works in your projects.

## Quick Start

Requires Python 3.11+. No dependencies beyond stdlib.

```bash
# Clone
git clone https://github.com/poelsen/claude-foundry.git
cd claude-foundry

# Initialize a project (interactive — detects languages, suggests config)
python3 tools/setup.py init /path/to/your/project

# Re-apply saved config to all known projects
python3 tools/setup.py update-all
```

`setup.py init` scans your project, detects languages and frameworks, then presents a selection menu for rules, agents, hooks, skills, and plugins. Selections are saved to `.claude/setup-manifest.json` so `update-all` can re-apply non-interactively.

## What Gets Installed

Everything is copied into your project's `.claude/` directory:

| Component | Source | Purpose |
|-----------|--------|---------|
| **Rules** | `rules/` + `rule-library/` | Coding standards, security, git workflow, testing |
| **Agents** | `agents/` | Specialized sub-agents (TDD, code review, security, architecture) |
| **Commands** | `commands/` | Slash commands (`/snapshot`, `/learn`, `/recall`, `/update-codemaps`) |
| **Skills** | `skills/` | Domain knowledge (GUI threading, ClickHouse, learned patterns) |
| **Hooks** | `hooks/` | Pre/post tool hooks (formatters, type checkers, git guards) |
| **Plugins** | — | LSP servers, workflow plugins (feature-dev, PR review) |

## Structure

```
claude-foundry/
├── rules/                    # Base rules (loaded for all projects)
├── rule-library/             # Modular rules (selected per-project)
│   ├── lang/                 # Python, C, C++, Rust, Go, React, Node.js, etc.
│   ├── domain/               # Embedded, DSP/audio, GUI, GUI threading
│   ├── style/                # Backend, scripts, library, data pipeline
│   ├── arch/                 # REST API, React app, monolith
│   ├── platform/             # GitHub
│   └── security/             # Sandbox, internal, enterprise
├── agents/                   # Agent definitions (16 agents)
├── commands/                 # Slash commands
├── skills/                   # Domain skills + learned patterns
│   └── learned/              # Patterns extracted via /learn
├── hooks/                    # Global hooks + per-project hook library
├── mcp-configs/              # MCP server configurations
├── tools/setup.py            # Setup and deployment tool
└── VERSION                   # CalVer version (YYYY.MM.DD[.N])
```

## Commands

Available in any project after running `setup.py init`:

| Command | Purpose |
|---------|---------|
| `/snapshot` | Capture, restore, or list session context snapshots |
| `/learn` | Extract reusable patterns from the current session |
| `/recall` | Search and surface previously learned patterns |
| `/update-codemaps` | Generate or refresh architecture codemaps |

## Agents

Agents are specialized sub-agents launched via the `Task` tool. Selected per-project based on language:

| Agent | Languages |
|-------|-----------|
| `architect-*` | Python, TypeScript |
| `tdd-guide-*` | Python, TypeScript |
| `code-reviewer-*` | Python, TypeScript |
| `security-reviewer-*` | Python, TypeScript |
| `build-error-resolver-*` | Python, TypeScript |
| `e2e-test-*` | Python (web + Qt), TypeScript |
| `refactor-cleaner-*` | Python, TypeScript |
| `doc-updater` | All |

## Hooks

### Global (all projects)

- **Dev server blocker** — blocks dev servers outside tmux
- **tmux reminder** — suggests tmux for long-running commands
- **git push pause** — pauses before push for review
- **doc blocker** — blocks creation of unnecessary documentation files
- **PR creation logger** — logs PR URL after `gh pr create`
- **JSON validator** — validates JSON after editing .json files
- **Auto-snapshot** — captures session context before compaction and on exit

### Per-project (opt-in via `setup.py`)

Located in `hooks/library/`. Activated based on detected languages:

| Hook | Language |
|------|----------|
| `ruff-format.sh` | Python |
| `mypy-check.sh` | Python |
| `prettier-format.sh` | JS/TS |
| `tsc-check.sh` | TypeScript |
| `cargo-check.sh` | Rust |

## Learned Skills

The `/learn` command extracts reusable patterns from your sessions and saves them as skills:

- **Shared** (`skills/learned/<category>/`): Committed to this repo, deployed to all projects
- **Project-local** (`.claude/skills/learned-local/`): Stays in the project

Use `/recall` to search learned skills. Claude also checks them automatically when stuck (via `rules/skills.md`).

## Versioning

CalVer: `YYYY.MM.DD` with `.N` suffix for same-day releases. Bumped automatically by GitHub Actions on merge to `master`.

## Credits

Inspired by [everything-claude-code](https://github.com/affaan-m/everything-claude-code) by Affaan M.

## License

MIT
