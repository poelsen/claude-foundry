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
   - **Modular rules** — language tooling, project templates, platform, security
   - **Hooks** — language-specific formatters and type checkers
   - **Agents** — specialized sub-agents matched to your languages
   - **Skills** — domain knowledge modules
   - **Plugins** — LSP servers, workflow plugins
3. Copies selected files into your project's `.claude/` directory
4. Saves selections to `.claude/setup-manifest.json` for future updates

## Updating

From any configured project, run the `/update-foundry` slash command inside a Claude Code session:

```
/update-foundry                # Check for new release, download, and apply
/update-foundry-check          # Just check if an update is available
/update-foundry-interactive    # Full interactive menu to add/change selections
```

`/update-foundry` checks the GitHub releases API, downloads the latest tarball, extracts it to **`<project>/.claude/foundry/`**, and runs that extracted setup.py non-interactively using the saved manifest. Works the same regardless of how you bootstrapped.

### Where foundry lives after install

Every project gets its own pinned copy of the foundry source tree at:

```
<project>/.claude/foundry/
├── tools/setup.py                    # this project's setup.py (pinned)
├── tools/install-copilot-mcp.sh
├── rules/ rule-library/ agents/ commands/ skills/ hooks/
├── mcp-configs/
└── vscode-copilot-mcp/               # extension source + pre-built .vsix
```

**Why per-project?** Different projects can be on different foundry versions, and `setup.py` is always matched to the rest of the tree on disk. No user-level cache, no symlinks — one self-contained copy per project. You can delete the original bootstrap tarball immediately after the first `setup.py init`; everything you need is under `.claude/foundry/` from that point on.

The tree is refreshed atomically on every `/update-foundry` (staged under `.claude/.foundry.new/`, swapped into place only after a successful setup run; rolled back on failure).

### Manual re-init

To re-run setup.py manually (e.g. to toggle new skill groups, register a private source, or reconfigure):

```bash
python3 <project>/.claude/foundry/tools/setup.py init <project>
```

The post-init summary prints this exact command so you can copy-paste it from your terminal.

For batch updates across all known projects:

```bash
python3 <project>/.claude/foundry/tools/setup.py update-all
```

## CLAUDE.md Convention

When `setup.py init` runs, it handles `CLAUDE.md` intelligently:

### For new projects (no CLAUDE.md)

Creates a minimal `CLAUDE.md` with a **claude-foundry header** containing:
- List of deployed rules with descriptions
- Environment commands for detected languages (setup, test, lint)
- Pointers to `codemaps/INDEX.md` for architecture
- Documentation conventions

### For existing projects

If `CLAUDE.md` already exists, setup.py offers three options:

| Option | Behavior |
|--------|----------|
| **Replace** | Generate new CLAUDE.md, save original as `CLAUDE.md.old` |
| **Merge** | Prepend claude-foundry header to existing, save original as `CLAUDE.md.old` |
| **Quit** | Abort setup entirely |

### Header updates

The claude-foundry header is wrapped in marker comments (`<!-- claude-foundry -->` ... `<!-- /claude-foundry -->`). On subsequent runs:
- If the marker exists, the header is **updated silently** with current rules/languages
- If no marker exists, setup.py asks before modifying (interactive) or skips (non-interactive)

### Best practices

- Keep `CLAUDE.md` minimal — just pointers and environment commands
- The header points Claude to the right places automatically

## Documentation Structure

Claude-foundry recommends a three-tier documentation approach:

| Location | Purpose | Maintained by |
|----------|---------|---------------|
| `CLAUDE.md` | Pointers and environment setup | claude-foundry (auto-updated) |
| `codemaps/` | Architecture overview per module | `/update-codemaps` (auto-generated) |
| `docs/` | Detailed project documentation | You (manual) |

### CLAUDE.md

Keep minimal. The claude-foundry header provides:
- Links to `.claude/rules/` for coding standards
- Environment commands (setup, test, lint)
- Pointer to `codemaps/INDEX.md`

Don't put detailed documentation here — it gets out of sync and wastes context.

### codemaps/

Auto-generated architecture docs. Run `/update-codemaps` to create/refresh. Each module gets:
- Purpose and responsibilities
- Key components with file:line references
- Public API surface
- Dependencies and data flow

Claude reads these before modifying unfamiliar code.

### docs/

Your detailed documentation:
- `docs/ARCHITECTURE.md` — design decisions, patterns, rationale
- `docs/DEVELOPMENT.md` — setup guide, workflow, conventions
- `docs/API.md` — detailed API documentation

If you have existing documentation in `CLAUDE.md`, migrate it to `docs/` after running setup.py init

## Codemaps

Codemaps are auto-generated architecture documentation. Each module gets a markdown file describing key components, public APIs, dependencies, and data flow.

### Using codemaps

1. Run `/update-codemaps` to generate or refresh architecture docs
2. Files are created in `codemaps/` with an `INDEX.md` overview
3. The command checks staleness — only stale codemaps regenerate

### When to update

Run `/update-codemaps` after:
- Adding new modules or packages
- Changing public APIs
- Adding significant new dependencies

Claude automatically reads `codemaps/INDEX.md` before modifying unfamiliar modules (per the `codemaps.md` rule).

## What Gets Installed

Everything is copied into `<project>/.claude/`:

| Component | Source | What it does |
|-----------|--------|--------------|
| **Rules** | `rules/` + `rule-library/` | Markdown files that instruct Claude on coding standards, security, git workflow, testing methodology |
| **Agents** | `agents/` | Specialized sub-agents for TDD, code review, security analysis, architecture design |
| **Commands** | `commands/` | Slash commands: `/snapshot`, `/learn`, `/learn-recall`, `/update-foundry`, `/update-codemaps` |
| **Skills** | `skills/` | Domain knowledge modules (GUI threading patterns, ClickHouse, learned patterns) |
| **Hooks** | `hooks/library/` | Shell scripts that run before/after Claude Code tool calls (formatters, type checkers) |
| **Plugins** | configured in `settings.json` | LSP servers and workflow plugins (feature-dev, PR review toolkit) |
| **Copilot MCP** (opt-in) | `vscode-copilot-mcp/` | VS Code extension + MCP bridge that routes tasks to Copilot models. Disabled by default. See [Copilot MCP](#copilot-mcp-opt-in). |

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
| `lang/` | Python, Node.js, Go, Rust, MATLAB |
| `templates/` | Embedded C, Embedded DSP, React App, REST API, Desktop GUI Qt, Library, Scripts, Data Pipeline, Monolith |
| `platform/` | GitHub (auto-detected) |
| `security/` | Sandbox, internal, enterprise |

## Commands

Slash commands are available inside Claude Code after running `setup.py init`:

| Command | What it does |
|---------|--------------|
| `/snapshot` | Captures current session state (task, decisions, files modified, next steps) to a snapshot file. |
| `/snapshot-list` | Lists all snapshots with date, goal, and status. |
| `/snapshot-restore` | Resumes from the most recent snapshot. |
| `/learn` | After solving a non-trivial problem, extracts the pattern into a reusable skill file. See [Learned Skills](#learned-skills). |
| `/learn-recall` | Lists or searches all learned skills. `/learn-recall python` searches for Python-related patterns. |
| `/update-foundry` | Checks GitHub for a newer release and applies it. See [Updating](#updating). |
| `/update-foundry-check` | Checks if an update is available without applying changes. |
| `/update-foundry-interactive` | Full interactive menu to add or change component selections. |
| `/update-codemaps` | Generates or refreshes architecture documentation per module. |
| `/private-list` | Lists registered private config sources with status. |
| `/private-remove` | Removes a private source by prefix. `/private-remove company` removes all `company-*` files. |
| `/prj-new <name>` | Creates a new named project in `.claude/prjs/<name>.md`. See [Project Management](#project-management). |
| `/prj-list` | Lists all named projects with status and resume commands. |
| `/prj-pause <name>` | Saves current session state and marks the project paused. |
| `/prj-resume <name>` | Loads a project's context and resumes work (suggests `--resume <session_id>`). |
| `/prj-done <name>` | Marks a project complete. |
| `/prj-delete <name>` | Deletes a project file. |

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


## Skill Selection (groups, hidden skills, gating)

The skill menu in `setup.py init` presents related skills as **groups**, not individual toggles. Selecting a group toggles all its members together:

| Group | Members |
|-------|---------|
| **Megamind Reasoning** | `megamind-deep`, `megamind-creative`, `megamind-adversarial`, `megamind-financial` |
| **Project Management** | `prj-new`, `prj-list`, `prj-pause`, `prj-resume`, `prj-done`, `prj-delete` |

Both groups are **auto-selected by default**. Individual non-grouped skills (`clickhouse-io`, `gui-threading`, `learn`, `update-foundry`, `snapshot-list`, `private-list`, `private-remove`, etc.) continue to appear as individual entries.

**Hidden skills (gated on MCP selection):** the 7 `copilot-*` skills do NOT appear in the skill selection menu. They're installed automatically when (and only when) you toggle `copilot-mcp` ON in the **MCP servers** menu — because a slash command like `/copilot-ask` is useless without the extension + bridge, so it never makes sense to select them individually. Deselecting `copilot-mcp` in the MCP menu strips all 7 in one step.

The manifest still stores individual skill names (not group names), so existing projects keep working without migration.

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

## Private Sources

Private sources let you add company-specific or team-specific rules, commands, skills, agents, and hooks alongside the public claude-foundry config. Register once, and they're automatically re-applied on every `/update-foundry`.

### Directory structure

A private source follows the same layout as claude-foundry:

```
my-company-config/
├── rule-library/          # Rules deployed to .claude/rules/
│   └── templates/
│       └── custom-dsp.md
├── commands/              # Optional slash commands
├── skills/                # Optional skill directories
├── agents/                # Optional agents
└── hooks/
    └── library/           # Optional hooks
```

### Registering a private source

**During interactive init:**
```bash
python3 tools/setup.py init /path/to/project
# ... normal setup ...
# Add a private config source? (path or Enter to skip): /path/to/company-config
# Prefix [company-config]: company
# ... toggle menu for available items ...
```

**Via CLI flags:**
```bash
python3 tools/setup.py init /path/to/project \
  --private /path/to/company-config --prefix company
```

Multiple sources can be registered. Files are deployed with the prefix to avoid collisions (e.g., `company-custom-dsp.md`).

### Managing private sources

| Command | What it does |
|---------|--------------|
| `/private-list` | Show registered sources with deployed file counts |
| `/private-remove <prefix>` | Remove all files with that prefix and unregister |

### How it works

- Selections are saved in `setup-manifest.json` under `"private_sources"`
- `setup.py init --non-interactive` re-deploys from the manifest automatically
- `/update-foundry` calls `setup.py init --non-interactive`, so private sources survive updates
- Foundry's cleanup functions skip private-prefixed files
- Paths are absolute and machine-specific — each team member registers their own local path

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
│   ├── lang/                 # Language tooling rules
│   ├── templates/            # Project type templates
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

## Megamind Skills

The megamind skills are reasoning enhancers that improve Claude's performance on complex tasks. Each mode targets a different thinking style.

### Modes

| Mode | Purpose | Best For |
|------|---------|----------|
| **megamind-deep** | Systematic analysis — surface assumptions, consider alternatives, assess risks | Architecture decisions, debugging, scope clarification |
| **megamind-creative** | Structured creative chaos — pattern-mining, analogies, constraint mutation | Creative problem-solving, brainstorming, unconventional solutions |
| **megamind-adversarial** | Red-team — attack the obvious approach, find failure modes, stress-test | Security review, design review, finding weaknesses |
| **megamind-financial** | Multi-domain financial analysis — investment valuation (Thorleif Jackson methodology), DK/DE tax planning, mortgage, pension, insurance | Stock valuation, tax optimization, loan/mortgage analysis, retirement planning |

`megamind-deep` and `megamind-creative` are auto-selected during `setup.py init`. The adversarial and financial variants are opt-in.

The `megamind-financial` skill uses country-specific data files in `skills/megamind-financial/data/` (e.g., `dk-tax-2026.md`). See [skills/IMPROVEMENT-PROCESS.md](skills/IMPROVEMENT-PROCESS.md) for the annual DK tax data update procedure.

### Benchmark (Opus 4.6, 30 challenges, 5 runs each)

Skills are evaluated using a Claude-as-judge benchmark. Each challenge has a rubric with required elements and anti-patterns. The judge scores each response and the benchmark reports hit rates, pass rates, and averages.

**Overall:**

| Mode | Avg Score | Pass Rate | Delta vs Baseline |
|------|-----------|-----------|-------------------|
| Baseline (no skill) | 5.0 | 62% | — |
| megamind-deep | 6.7 | 82% | +1.7 |
| megamind-creative | 6.4 | 78% | +1.4 |
| megamind-adversarial | 6.5 | 80% | +1.5 |

**Per-category winners:**

| Category | Description | Best Mode | Score |
|----------|-------------|-----------|-------|
| adversarial | Red-team designs (auth, caching, pipelines, feature flags) | adversarial | 7.7 |
| arch | Architecture under ambiguity (DR, build-vs-buy, event-driven, gateways) | deep | 7.3 |
| creative | Creative problem-solving (alert fatigue, code review, onboarding, CLI) | creative | 8.0 |
| cross | Cross-cutting (stakeholder conflicts, incidents, security breaches, tech debt) | deep | 9.5 |
| deep | Deep reasoning (DB migration, refactoring, API design, testing, deploys) | deep | 7.0 |
| scope | Scope clarification for vague requests ("make it faster", "fix search") | adversarial | 2.6 |

Each skill dominates its target category. Deep mode is the best all-rounder. Scope challenges expose a fundamental weakness — Opus jumps to solutions instead of asking clarifying questions for vague prompts, even with skills active.

### Challenge Format

Challenges are YAML files in `tests/challenges/`:

```yaml
id: arch-001
name: "Architecture Decision Under Ambiguity"
category: reasoning_depth
skill: megamind-deep
prompt: |
  Add real-time notifications to our Django app...
rubric:
  required_elements:
    identifies_assumptions: "Lists assumptions about scale, notification types"
    considers_alternatives: "Mentions at least 2 architectural approaches"
  anti_patterns:
    jumps_to_code: "Immediately writes implementation code"
  passing_score: 6
```

### Running the Benchmark

Requires the `claude` CLI authenticated and in PATH. Uses `--output-format json` and `--permission-mode bypassPermissions` for non-interactive / CI-compatible execution.

```bash
# Full run (76 challenges x 5 modes x 5 runs)
python3 tools/run_benchmark.py --workers 24 --runs 5 --save results/output.json

# Single challenge
python3 tools/run_benchmark.py --runs 1 --challenges arch-001

# Specific skill (always includes baseline for comparison)
python3 tools/run_benchmark.py --skill megamind-deep --runs 3

# Financial skill only
python3 tools/run_benchmark.py --skill megamind-financial --runs 2

# Compare against saved baseline
python3 tools/run_benchmark.py --runs 5 --save results/new.json --compare results/old.json
```

## Copilot MCP (opt-in)

Route Claude Code tasks to VS Code Copilot models (Claude Opus/Sonnet 4.6, GPT-5.4, Gemini 3.1, Grok, etc.) via an MCP bridge. Saves Anthropic API tokens by using your existing GitHub Copilot subscription. **Disabled by default** — selecting `copilot-mcp` in the MCP-servers toggle during `setup.py init` enables the whole thing: 7 slash-command skills, MCP server registration, and installing the VS Code extension.

> **⚠ Runtime requirements — read this before you try the commands:**
>
> Every time you want to use a `/copilot-*` slash command, **all of these must be true**:
>
> 1. **VS Code is running** on your machine
> 2. **The project folder is opened** as a workspace in VS Code (File → Open Folder)
> 3. **Claude Code is launched from within that workspace tree** — the MCP bridge walks up from your cwd looking for `.vscode/copilot-mcp.json`. If Claude Code runs from `~/unrelated/` while VS Code has `~/my-project/` open, the bridge will not find the extension.
> 4. **The extension is enabled for that workspace** — see the "Enable per workspace" step below. The extension is installed machine-wide but **idle by default**; it only starts when a workspace's `.vscode/settings.json` opts in.
>
> Without all four, `/copilot-*` commands fail with "extension not reachable". Closing VS Code stops the bridge until you reopen the workspace.

### Components

- **VS Code extension** — HTTP server inside VS Code that proxies to the `vscode.lm` API (forces `vendor: copilot`)
- **MCP bridge** — Node.js stdio server that forwards Claude Code tool calls to the extension's HTTP endpoint
- **7 slash-command skills**: `/copilot-list-models`, `/copilot-ask`, `/copilot-review`, `/copilot-audit`, `/copilot-agent`, `/copilot-multi`, `/copilot-job`

### Install

During `setup.py init`, toggle `copilot-mcp` in the MCP-servers menu. That single decision does everything:

1. Writes the `copilot-mcp` entry to `.claude.json` with an absolute path to `<foundry>/vscode-copilot-mcp/mcp/server.js`
2. Auto-selects all 7 `copilot-*` skills for deployment to `.claude/skills/`
3. Runs [`tools/install-copilot-mcp.sh`](tools/install-copilot-mcp.sh) to install the VS Code extension:
   - Interactive mode: prompts before installing
   - Non-interactive mode (e.g. `/update-foundry`): auto-runs if all prereqs are present, skips gracefully with a clear notice if not

The install script uses a **pre-built `.vsix`** when available (shipped in every foundry release tarball, built by CI) — in that case the install is just `code --install-extension vscode-copilot-mcp-*.vsix --force` plus `npm install` in the MCP bridge directory. If you're on a bare git clone with no pre-built .vsix, the script falls back to the full build chain (`npm install` → `tsc` → `vsce package`). Both paths are idempotent.

To **disable** Copilot MCP on a project that previously had it enabled, run `setup.py init` interactively and toggle `copilot-mcp` OFF in the MCP-servers menu. Setup.py will strip the copilot-* skills and remove the MCP entry from `.claude.json`. Optionally also remove the `copilot-mcp.autoStart` line from the workspace's `.vscode/settings.json` and uninstall the extension from VS Code.

### Requirements

- VS Code with GitHub Copilot Chat (paid subscription with model access)
- Node.js >= 20
- **`code` shell command on PATH** — this is the *external* `code` executable used by `code --install-extension <vsix>`, NOT the integrated terminal panel inside VS Code. Install via VS Code: `Ctrl+Shift+P` → `Shell Command: Install 'code' command in PATH`, then restart your shell.
- `bash`, `curl`, `python3`, `awk`, `mktemp` (for background-job watcher; standard on Linux/macOS/WSL/Git Bash)

> **WSL caveat**: the `code` command from VS Code Server (`~/.vscode-server/bin/<hash>/bin/remote-cli/code`) only works **inside an integrated VS Code terminal session**, not from a plain WSL bash. If you're on WSL: open VS Code with your WSL workspace attached, open a terminal panel inside VS Code (`Ctrl+\``), and run `bash <project>/.claude/foundry/tools/install-copilot-mcp.sh` from *that* terminal. The integrated terminal sets up `PATH` so `code` is available.

### After install (REQUIRED — the extension is disabled by default)

1. **Enable the extension for your workspace.** In the project root, add or edit `.vscode/settings.json`:

   ```json
   {
     "copilot-mcp.autoStart": true
   }
   ```

   The extension is installed machine-wide but **idle by default** — it only starts the HTTP bridge in workspaces where you explicitly opt in via this setting. This prevents it from running in unrelated VS Code windows.

2. **Restart Claude Code** (MCP server processes are spawned at startup)

3. **Open the target workspace in VS Code** — the extension now auto-starts (because of step 1) and writes `.vscode/copilot-mcp.json`

4. From Claude Code in that workspace: `/copilot-list-models` — should return ~20 models

5. Add to the project's `.gitignore`:
   ```
   .vscode/copilot-mcp.json
   .vscode/copilot-mcp-sessions/
   ```

6. First LM request triggers a one-time VS Code "Allow" popup granting the extension LM API access — click Allow. It persists for the VS Code session.

You can verify the extension is installed and its state from the VS Code Extensions panel (`Ctrl+Shift+X` → search "Copilot MCP"). Its logs are in `Output → Copilot MCP`.

### Usage

All seven commands are available inside Claude Code once the extension is running. Claude Code must be launched from the same workspace tree that VS Code has open (the MCP bridge discovers the extension via `.vscode/copilot-mcp.json` by walking up from the cwd).

| Command | Purpose | Example |
|---------|---------|---------|
| `/copilot-list-models` | List available Copilot models with capabilities | `/copilot-list-models` |
| `/copilot-ask <model> <prompt>` | One-shot stateless question to any model | `/copilot-ask gpt-5.4 Explain tail call optimization` |
| `/copilot-review [model] [target]` | Code review on a file or diff | `/copilot-review claude-sonnet-4.6 src/auth.py` |
| `/copilot-audit [skill] [model] [target]` | Adversarial audit using a chosen skill | `/copilot-audit security gpt-5.4 src/api/` |
| `/copilot-agent [model] [session:name] <task>` | Autonomous agent loop with workspace tools | `/copilot-agent claude-opus-4.6 "Add retry logic to the HTTP client and run tests"` |
| `/copilot-multi [models:list] <task>` | Fan-out a task to multiple models in parallel | `/copilot-multi claude-opus-4.6,gpt-5.4,gemini-3.1 "Review this design doc"` |
| `/copilot-job [start\|status\|list] <args>` | Manage long-running background jobs | `/copilot-job start opus "Refactor the billing module"` |

**Model names** are whatever `/copilot-list-models` returns for your subscription. Typical options: `claude-opus-4.6`, `claude-sonnet-4.6`, `gpt-5.4`, `gpt-4.1`, `gemini-3.1`, `grok-code-fast-1`.

**When to use the agent vs. job modes:**
- Sync `copilot-agent`: tasks under ~5 minutes. Blocks until done.
- Background `copilot-job`: long tasks (refactors, audits). MCP tool call returns immediately; a bash watcher polls for completion and notifies Claude Code. Don't have the model poll `copilot-job status` in a loop — use the watcher.

**When to use `copilot-multi`:** when you want independent perspectives on the same question. Opus tends to find architectural/subtle issues; GPT-5.4 tends to find operational issues; Grok is fast and blunt. Feeding all three reports back to Opus for meta-analysis is an effective pattern.

### Updating

When you run `/update-foundry` in Claude Code (or `setup.py init` non-interactively), the updater:

1. Downloads the latest foundry tarball (which includes both `vscode-copilot-mcp/` source AND the pre-built `vscode-copilot-mcp-*.vsix`)
2. Redeploys skills and re-writes `.claude.json`
3. **Auto-installs the pre-built extension** if `copilot-mcp` is in your manifest AND all prereqs (`code`, `node`, `npm`, etc.) are present on PATH. The install script detects the pre-built .vsix, skips the build chain, and runs `code --install-extension --force`. Keeps the installed extension in sync with the foundry release without a manual step.

If a prereq is missing (e.g. running updates from a headless CI machine with no VS Code), the updater prints a skip message and the manual command to run later — the update itself still succeeds.

Your per-workspace `.vscode/settings.json` with `copilot-mcp.autoStart: true` is **not touched** by updates — your enable state persists across foundry releases.

Restart Claude Code after any update that reinstalled the extension so the MCP server picks up the new bridge.

### Troubleshooting

| Problem | Fix |
|---------|-----|
| `/copilot-list-models` says "extension not reachable" | Check the 4 runtime requirements (top of this section). Most common cause: `.vscode/settings.json` missing `copilot-mcp.autoStart: true`, so the extension is idle. Second most common: VS Code has a *different* folder open than the one Claude Code is running from. |
| Extension installed but server doesn't start | `copilot-mcp.autoStart` is `false` (the default). Add `{ "copilot-mcp.autoStart": true }` to the workspace's `.vscode/settings.json`, then reload VS Code (`Ctrl+Shift+P` → "Developer: Reload Window"). |
| 401 Unauthorized | Stale token from extension restart — restart Claude Code so the MCP bridge re-reads the token. |
| Empty response from a model | Should not happen; extension forces `vendor: 'copilot'`. If it does, check the VS Code output channel for `[copilot-mcp]`. |
| Port collision / `EADDRINUSE` | Someone set `copilot-mcp.port` to a fixed value. Set it back to `0` in VS Code settings (auto-assign). |
| Extension not built after update | Check prereqs with `command -v code node npm`. Run `bash tools/install-copilot-mcp.sh` manually once the missing tool is installed. |

Full troubleshooting table, tribal knowledge (VS Code LM API gotchas, Node fetch redirects, IPv6 SSRF, etc.), and the "deliberately-not-fixed" list are in [`vscode-copilot-mcp/FOUNDRY-INTEGRATION.md`](vscode-copilot-mcp/FOUNDRY-INTEGRATION.md).

### Testing

The extension ships with 58 unit tests (`src/pure.test.ts`) using Node's built-in test runner:

```bash
cd vscode-copilot-mcp
npm install
npm test                # 58 tests, ~60ms
npm run test:coverage   # 100% line coverage on pure.ts
```

The extension tests run as a dedicated GitHub Actions job (`vscode-copilot-mcp-tests` in `.github/workflows/pr-check.yml`) on every PR — independent from the Python pytest job so a TS failure gives a clear, separately-labeled signal in the PR UI.

## Project Management

Named project contexts let you juggle multiple parallel initiatives without losing state between sessions. Each project lives in `.claude/prjs/<name>.md` — a simple markdown file with YAML frontmatter tracking goal, status, decisions, key files, and the last Claude session ID.

### Workflow

```
/prj-new bank-refactor          # Create project, open file for editing
/prj-pause bank-refactor        # Save state (records current session_id)
/prj-list                       # See all projects, their status, resume commands
/prj-resume bank-refactor       # Reload context — suggests `claude --resume <id>`
/prj-done bank-refactor         # Mark complete
/prj-delete bank-refactor       # Remove
```

### Project file

A project file looks like:

```markdown
---
name: bank-refactor
status: active            # active | paused | done
updated: 2026-04-04T14:22
session_id: abc123...     # Set on /prj-pause
---

## Goal
Migrate the legacy /api/accounts endpoints to the new service.

## Status
- [x] Inventoried existing callers
- [ ] Draft compatibility shim
- [ ] Migration plan

## Decisions
- Use adapter pattern rather than parallel rewrite

## Key Files
- src/api/accounts.py
- tests/test_accounts.py

## Resume
What to pick up next session...
```

### How session tracking works

On `/prj-pause`, the script records the current Claude session ID into the project file via the shared `skills/_lib/session-id.sh` library (it reads `.claude/projects/<encoded-cwd>/` to find the active session JSONL). On `/prj-resume`, the skill reads it back and suggests `claude --resume <session_id>` so you can continue the exact same conversation — or start a fresh session with full project context loaded.

### When to use this vs `/snapshot`

| Feature | Use `/prj-*` | Use `/snapshot` |
|---------|--------------|-----------------|
| Long-lived named initiative | ✓ | |
| Running multiple projects in parallel | ✓ | |
| Point-in-time session capture | | ✓ |
| Stateful session resumption by ID | ✓ | |

All `prj-*` skills are auto-installed by `setup.py`.

## Credits

Inspired by [everything-claude-code](https://github.com/affaan-m/everything-claude-code) by Affaan M.

## License

MIT
