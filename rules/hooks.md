# Hooks System

## Hook Types

- **PreToolUse**: Before tool execution (validation, blocking)
- **PostToolUse**: After tool execution (validation, logging)
- **PreCompact**: Before context compaction (snapshot capture)
- **SessionEnd**: On session termination (snapshot capture)

## Active Hooks (in hooks/hooks.json)

### PreToolUse
- **Dev server blocker**: Blocks dev servers (npm/pnpm/yarn/bun run dev) outside tmux
- **tmux reminder**: Suggests tmux for long-running commands (npm, cargo, pytest, etc.)
- **git push pause**: Pauses before git push for review
- **doc blocker**: Blocks creation of unnecessary .md/.txt files

### PostToolUse
- **PR creation**: Logs PR URL and review command after `gh pr create`
- **JSON validation**: Validates JSON syntax after editing .json files

### PreCompact
- **Auto-snapshot**: Captures session context before compaction (5-min cooldown)

### SessionEnd
- **Auto-snapshot**: Captures session context on exit

## Per-Project Hooks

Formatters and type checkers are per-project. Add to your project's `.claude/settings.json` to opt in. See `hooks/library/README.md` for setup instructions.

Available scripts:
- `ruff-format.sh` — Python formatting
- `prettier-format.sh` — JS/TS formatting
- `tsc-check.sh` — TypeScript type checking
- `mypy-check.sh` — Python type checking
- `cargo-check.sh` — Rust type checking
