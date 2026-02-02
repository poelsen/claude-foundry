# Performance Optimization

## Model Selection Strategy

- **Opus** (default): All primary work — planning, architecture, debugging, code review, anything requiring judgment
- **Sonnet**: Well-scoped, low-ambiguity tasks — single-file edits, straightforward bug fixes, docs updates
- **Haiku**: Only where agent definition explicitly specifies it — formatting, linting, mechanical transforms

## Search Strategy

Claude Code's built-in Grep tool uses ripgrep (`rg`). No external search tools needed.

- **Direct Grep/Glob**: Exact pattern matches, known symbol names, specific file lookups
- **Explore agent**: Open-ended exploration, multi-round searches, "where is X handled?"
- **Sonnet/Haiku agents**: Delegate mechanical search loops (grep + read) to lower-cost models

Use Opus for research requiring judgment (viability analysis, architecture review, pattern evaluation). Prefer Explore agents over repeated Grep calls when the search scope is uncertain.

## Context Window Management

Avoid last 20% of context window for:
- Large-scale refactoring
- Feature implementation spanning multiple files
- Debugging complex interactions

Lower context sensitivity tasks:
- Single-file edits
- Independent utility creation
- Documentation updates
- Simple bug fixes

## Ultrathink + Plan Mode

For complex tasks requiring deep reasoning:
1. Use `ultrathink` for enhanced thinking
2. Enable **Plan Mode** for structured approach
3. "Rev the engine" with multiple critique rounds
4. Use split role sub-agents for diverse analysis
