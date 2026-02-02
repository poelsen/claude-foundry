# Agent Orchestration

## Available Agents

Located in `.claude/agents/` (per-project, installed by setup.py):

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| architect-typescript | TS/JS system design | TS/JS architectural decisions |
| architect-python | Python system design | Python architectural decisions |
| tdd-guide-typescript | TS/JS test-driven development | New TS/JS features, bug fixes |
| tdd-guide-python | Python test-driven development | New Python features, bug fixes |
| code-reviewer-typescript | TS/JS code review | After writing TS/JS code |
| code-reviewer-python | Python code review | After writing Python code |
| security-reviewer-typescript | TS/JS security analysis | Before TS/JS commits |
| security-reviewer-python | Python security analysis | Before Python commits |
| build-error-resolver-typescript | Fix TS/JS build errors | When tsc, eslint, Next.js build fails |
| build-error-resolver-python | Fix Python build errors | When mypy, ruff, pytest fails |
| e2e-test-typescript | TS/JS browser E2E (Playwright) | Web app user flows (TS/JS) |
| e2e-test-python-web | Python browser E2E (Playwright) | Web app user flows (Python) |
| e2e-test-python-qt | Python desktop GUI E2E (pytest-qt) | PySide6/PyQt widget testing |
| refactor-cleaner-typescript | TS/JS dead code cleanup | TS/JS code maintenance |
| refactor-cleaner-python | Python dead code cleanup | Python code maintenance |
| doc-updater | Documentation and codemaps | Updating docs and codemaps (uses /update-codemaps) |


## Plugin Agents

Auto-discovered from installed plugins:
- **feature-dev** — 7-phase feature workflow
- **pr-review-toolkit** — PR analysis suite
- **code-review** — automated PR feedback
- **code-simplifier** — autonomous refactoring

## Immediate Agent Usage

No user prompt needed:
1. Complex feature requests - Use **plan mode** (built-in)
2. Code just written/modified - Use **code-reviewer** agent
3. Bug fix or new feature - Use **tdd-guide** agent
4. Architectural decision - Use **architect** agent

## Parallel Task Execution

ALWAYS use parallel Task execution for independent operations:

```markdown
# GOOD: Parallel execution
Launch 3 agents in parallel:
1. Agent 1: Security analysis of auth module
2. Agent 2: Performance review of cache system
3. Agent 3: Type checking of utils module

# BAD: Sequential when unnecessary
First agent 1, then agent 2, then agent 3
```

