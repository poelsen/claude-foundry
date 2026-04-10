---
name: copilot-review
description: Code review via Copilot agent with full workspace access. Usage: /copilot-review [model] [target]
---

# /copilot-review — Copilot Code Review

Run a code review using an autonomous Copilot agent that can read files, search code, and run commands in the workspace.

## Usage

```
/copilot-review [model] [target]
```

- **model**: Model family (default: `claude-sonnet-4.6`). Use `gpt-5.4` or `claude-opus-4.6` for deeper review.
- **target**: What to review — file path, module name, "recent changes", "staged changes", or a description. Default: unstaged git changes.

## Instructions

1. Parse arguments. If no target specified, the target is "unstaged git changes".
2. Build a review task prompt:

```
Review the following code for:
- Bugs, logic errors, off-by-one errors
- Security vulnerabilities (injection, auth bypass, data leaks)
- Error handling gaps (swallowed exceptions, missing validation)
- Code quality (naming, complexity, duplication)
- Correctness of business logic

Target: {target}

For each issue found:
- State the file and line/function
- Rate severity: CRITICAL / HIGH / MEDIUM / LOW
- Explain the real-world impact
- Suggest a fix

If reviewing git changes, first run `git diff` to see what changed, then review the full files for context.
```

3. Call `mcp__copilot-mcp__copilot_agent` with the task, the chosen model, and sessionId `"review"`.
4. Display results to user.
