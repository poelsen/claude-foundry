# Claude Code Foundry

> **Early alpha.** Under active development. The current rule set is most mature for **Python** and **PySide6/Qt** projects. Other languages (C, C++, Rust, Go, TypeScript) have base rules but are less battle-tested. Expect breaking changes.

A framework for configuring [Claude Code](https://docs.anthropic.com/en/docs/claude-code) across different project types and programming languages. Provides modular rules, specialized agents, reusable skills, tool hooks, and slash commands — all selected per-project based on what you're building.

## Bootstrap

Requires Python 3.11+. No external dependencies.

### Option A: Download a release

Download the latest tarball from the [Releases page](https://github.com/poelsen/claude-foundry/releases) and extract it:

```bash
tar xzf claude-foundry-*.tar.gz
cd claude-foundry-*
python3 tools/setup.py init /path/to/your/project
```

### Option B: Clone the repo

```bash
git clone https://github.com/poelsen/claude-foundry.git
cd claude-foundry
python3 tools/setup.py init /path/to/your/project
```

### What `setup.py init` does

1. Scans your project for languages (file extensions, config files like `pyproject.toml`, `package.json`, `Cargo.toml`)
2. Presents interactive toggle menus for each component category:
   - **Base rules** — coding style, security, testing, git workflow, etc.
   - **Modular rules** — language-specific, domain-specific, architecture patterns
   - **Hooks** — language-specific formatters and type checkers
   - **Agents** — specialized sub-agents matched to your languages
   - **Skills** — domain knowledge modules
   - **Plugins** — LSP servers, workflow plugins
3. Copies selected files into your project's `.claude/` directory
4. Saves selections to `.claude/setup-manifest.json` for future updates

## Updating

From any configured project, run the `/update-foundry` slash command inside a Claude Code session:

```
/update-foundry           # Check for new release, download, and apply
/update-foundry --check   # Just check if an update is available
```

`/update-foundry` checks the GitHub releases API, downloads the latest tarball, and re-runs `setup.py init` non-interactively using your saved selections from the manifest. Works the same regardless of how you bootstrapped.

You can also update manually:

```bash
# If you cloned the repo
cd claude-foundry && git pull
python3 tools/setup.py init /path/to/your/project

# Batch update all known projects
python3 tools/setup.py update-all
```

## What Gets Installed

Everything is copied into `<project>/.claude/`:

| Component | Source | What it does |
|-----------|--------|--------------|
| **Rules** | `rules/` + `rule-library/` | Markdown files that instruct Claude on coding standards, security, git workflow, testing methodology |
| **Agents** | `agents/` | Specialized sub-agents for TDD, code review, security analysis, architecture design |
| **Commands** | `commands/` | Slash commands: `/snapshot`, `/learn`, `/recall`, `/update-foundry`, `/update-codemaps` |
| **Skills** | `skills/` | Domain knowledge modules (GUI threading patterns, ClickHouse, learned patterns) |
| **Hooks** | `hooks/library/` | Shell scripts that run before/after Claude Code tool calls (formatters, type checkers) |
| **Plugins** | configured in `settings.json` | LSP servers and workflow plugins (feature-dev, PR review toolkit) |

## Rules

Rules are markdown files loaded by Claude Code at session start. They shape how Claude writes code, handles errors, makes commits, and reviews changes.

**Base rules** (`rules/`) are recommended for all projects:

- `coding-style.md` — KISS/YAGNI/DRY, small functions, minimal diffs
- `git-workflow.md` — branch naming, commit message format, PR workflow
- `security.md` — mandatory security checks before commits
- `testing.md` — TDD workflow, 80% coverage target
- `architecture.md` — composition over inheritance, module boundaries
- `performance.md` — model selection strategy, context window management
- `agents.md` — when and how to use specialized sub-agents
- `codemaps.md` — architecture documentation system
- `hooks.md` — documents available hooks
- `skills.md` — points Claude to learned patterns when stuck

**Modular rules** (`rule-library/`) are selected per-project:

| Category | Examples |
|----------|----------|
| `lang/` | Python, C, C++, Rust, Go, React, Node.js, MATLAB |
| `domain/` | Embedded, DSP/audio, GUI, GUI threading |
| `style/` | Backend, scripts, library, data pipeline |
| `arch/` | REST API, React app, monolith |
| `platform/` | GitHub (auto-detected) |
| `security/` | Sandbox, internal, enterprise |

## Commands

Slash commands are available inside Claude Code after running `setup.py init`:

| Command | What it does |
|---------|--------------|
| `/snapshot` | Saves current session state (task, decisions, files modified, next steps) to a markdown file. Use `/snapshot --restore` to resume after a restart or context compaction. Use `/snapshot --list` to see all snapshots. |
| `/learn` | After solving a non-trivial problem, extracts the pattern into a reusable skill file. Asks you to pick a category and save location. See [Learned Skills](#learned-skills) below. |
| `/recall` | Lists or searches all learned skills. `/recall python` searches for Python-related patterns. |
| `/update-foundry` | Checks GitHub for a newer release and applies it. See [Updating](#updating). |
| `/update-codemaps` | Generates or refreshes architecture documentation (one markdown file per module with key components, public API, dependencies, and data flow). |

## Agents

Agents are specialized sub-agents that Claude Code launches for specific tasks. During `setup.py init`, agents are selected based on your project's languages.

| Agent | Purpose | Languages |
|-------|---------|-----------|
| `architect-*` | System design and architectural decisions | Python, TypeScript |
| `tdd-guide-*` | Test-driven development (write tests first) | Python, TypeScript |
| `code-reviewer-*` | Code quality, security, maintainability review | Python, TypeScript |
| `security-reviewer-*` | OWASP scanning, vulnerability detection | Python, TypeScript |
| `build-error-resolver-*` | Fix build/lint/type errors with minimal diffs | Python, TypeScript |
| `e2e-test-*` | End-to-end browser or GUI testing | Python (Playwright + pytest-qt), TypeScript (Playwright) |
| `refactor-cleaner-*` | Dead code removal, consolidation | Python, TypeScript |
| `doc-updater` | Documentation and codemap updates | All |

## Hooks

Hooks are shell scripts that run automatically before or after Claude Code tool calls.

### What `setup.py` installs

`setup.py` writes hook entries into your project's `.claude/settings.json` based on detected languages. Only language-specific hooks from `hooks/library/` are installed:

| Hook script | Trigger | Language |
|-------------|---------|----------|
| `ruff-format.sh` | After editing `.py` files | Python |
| `mypy-check.sh` | After editing `.py` files | Python |
| `prettier-format.sh` | After editing `.ts`/`.tsx`/`.js`/`.jsx` files | JS/TS |
| `tsc-check.sh` | After editing `.ts`/`.tsx` files | TypeScript |
| `cargo-check.sh` | After editing `.rs` files | Rust |


## Learned Skills

Claude Code sessions often produce solutions worth remembering. The `/learn` and `/recall` commands turn these into persistent, searchable knowledge.

### How it works

1. After solving a non-trivial problem, run `/learn`
2. Claude analyzes the session and drafts a skill file (problem → solution → example → when to use)
3. You pick a **category** (e.g. `python`, `debugging`, `pyside6`) and a **save location**:
   - **Claude-foundry repo** (default): `skills/learned/<category>/<name>.md` — commit and push to share across machines. Deployed to projects via `setup.py init`.
   - **Project-local**: `.claude/skills/learned-local/<category>/<name>.md` — stays in this project only.
4. When Claude gets stuck on a problem, it checks these directories automatically (via `rules/skills.md`)
5. Run `/recall` to list all learned skills, or `/recall <keyword>` to search

The `skills/learned/` directory starts empty. Categories are created as you learn patterns.

## Releases

Every merge to `master` triggers a GitHub Actions workflow that:

1. Computes a [CalVer](https://calver.org/) version (`YYYY.MM.DD`, with `.N` suffix for same-day releases)
2. Creates a git tag
3. Builds a release tarball containing all deployable files
4. Publishes a [GitHub Release](https://github.com/poelsen/claude-foundry/releases) with the tarball attached

## Project Structure

```
claude-foundry/
├── rules/                    # Base rules (selected during init)
├── rule-library/             # Modular rules by category
│   ├── lang/                 # Language-specific rules
│   ├── domain/               # Domain-specific rules
│   ├── style/                # Project style rules
│   ├── arch/                 # Architecture pattern rules
│   ├── platform/             # Platform rules (GitHub)
│   └── security/             # Security level rules
├── agents/                   # Sub-agent definitions
├── commands/                 # Slash commands
├── skills/                   # Domain skills
│   └── learned/              # Patterns extracted via /learn
├── hooks/
│   ├── hooks.json            # Reference hooks (manual install)
│   └── library/              # Hook scripts (deployed by setup.py)
├── mcp-configs/              # MCP server configurations
└── tools/setup.py            # Setup and deployment tool
```

## Credits

Inspired by [everything-claude-code](https://github.com/affaan-m/everything-claude-code) by Affaan M.

## License

MIT
